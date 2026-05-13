#!/usr/bin/env python3
"""
Parallel Document Ingestion Pipeline for the CLaRa Legal Analysis System.

Ingests up to 3 documents simultaneously using separate threads,
each with its own Bedrock client and OpenSearch writer.

Usage:
    python ingest_parallel.py file1.pdf file2.pdf file3.pdf
    python ingest_parallel.py file1.pdf file2.pdf file3.pdf --clear
    python ingest_parallel.py file1.pdf file2.pdf file3.pdf --dir /path/to/documents
"""
import logging
import time
import hashlib
from pathlib import Path
from typing import Generator, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.table import Table
from pypdf import PdfReader

from config import config
from models import DocumentChunk, IngestionStats

logging.getLogger("pypdf").setLevel(logging.ERROR)

# Import modules based on configuration
if config.aws:
    from compression_agent_bedrock import BedrockCompressionAgent as CompressionAgent
else:
    from compression_agent import CompressionAgent

if config.aws and config.aws.opensearch_endpoint:
    from vector_store_opensearch import OpenSearchVectorStore as VectorStore
else:
    from vector_store import VectorStore

console = Console()
app = typer.Typer(help="CLaRa Parallel Document Ingestion (up to 3 files)")

# Shared lock for thread-safe console output and stats
_print_lock = Lock()


class DocumentLoader:
    """Loads and chunks PDF documents while preserving metadata."""

    def __init__(self, chunk_size: int = 2000, chunk_overlap: int = 200):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def load_pdf(self, pdf_path: Path) -> Generator[DocumentChunk, None, None]:
        reader = PdfReader(pdf_path)
        document_name = pdf_path.name

        pages_text = []
        for page_num, page in enumerate(reader.pages, start=1):
            text = page.extract_text() or ""
            if text.strip():
                pages_text.append((page_num, text))

        if not pages_text:
            return

        combined_text = ""
        page_boundaries = []
        for page_num, text in pages_text:
            start = len(combined_text)
            combined_text += text + "\n\n"
            end = len(combined_text)
            page_boundaries.append((start, end, page_num))

        chunks = self._create_chunks(combined_text)
        total_chunks = len(chunks)

        for chunk_idx, (start, end, text) in enumerate(chunks):
            chunk_pages = self._get_pages_for_range(start, end, page_boundaries)
            section_title = self._detect_section_title(text)
            chunk_id = hashlib.sha256(
                f"{document_name}:{chunk_idx}:{text[:100]}".encode()
            ).hexdigest()[:12]

            yield DocumentChunk(
                chunk_id=chunk_id,
                document_name=document_name,
                document_path=str(pdf_path.absolute()),
                page_numbers=chunk_pages,
                section_title=section_title,
                raw_text=text,
                chunk_index=chunk_idx,
                total_chunks=total_chunks
            )

    def _create_chunks(self, text: str) -> list[tuple[int, int, str]]:
        chunks = []
        start = 0
        while start < len(text):
            end = start + self.chunk_size
            if end < len(text):
                para_break = text.rfind("\n\n", start, end)
                if para_break > start + self.chunk_size // 2:
                    end = para_break + 2
                else:
                    for punct in [". ", ".\n", "? ", "?\n", "! ", "!\n"]:
                        sent_break = text.rfind(punct, start, end)
                        if sent_break > start + self.chunk_size // 2:
                            end = sent_break + len(punct)
                            break
            chunk_text = text[start:end].strip()
            if chunk_text:
                chunks.append((start, end, chunk_text))
            start = end - self.chunk_overlap
            if start >= len(text) - self.chunk_overlap:
                break
        return chunks

    def _get_pages_for_range(self, start: int, end: int, page_boundaries: list[tuple[int, int, int]]) -> list[int]:
        pages = []
        for page_start, page_end, page_num in page_boundaries:
            if start < page_end and end > page_start:
                pages.append(page_num)
        return pages or [1]

    def _detect_section_title(self, text: str) -> Optional[str]:
        lines = text.strip().split("\n")
        if not lines:
            return None
        first_line = lines[0].strip()
        if len(first_line) < 100:
            if any(first_line.upper().startswith(p) for p in
                   ["SECTION", "CHAPTER", "PART", "ARTICLE", "RULE", "REGULATION"]):
                return first_line
            if first_line and (first_line[0].isdigit() or first_line.startswith("§")):
                return first_line[:80]
            if first_line.isupper() and len(first_line) > 5:
                return first_line
        return None


def _process_one_document(
    pdf_path: Path,
    file_idx: int,
    total_files: int,
    progress: Progress,
    task_id: int,
) -> dict:
    """
    Process a single document end-to-end in its own thread.

    Each thread gets its own CompressionAgent and VectorStore instances
    so there's no contention on Bedrock or OpenSearch clients.
    """
    doc_name = pdf_path.name
    doc_start = time.time()

    # Per-thread instances — no shared state
    loader = DocumentLoader(
        chunk_size=config.documents.chunk_size,
        chunk_overlap=config.documents.chunk_overlap
    )
    compression_agent = CompressionAgent()
    vector_store = VectorStore()

    try:
        # Step 1: Load and chunk
        chunks = list(loader.load_pdf(pdf_path))
        if not chunks:
            with _print_lock:
                progress.update(task_id, description=f"[yellow]⚠ [{file_idx}/{total_files}] {doc_name} - no text", completed=100)
                console.print(f"[yellow]⚠ [{file_idx}/{total_files}] {doc_name} - no text extracted[/yellow]")
            return {"name": doc_name, "error": "no_text", "chunks": 0, "abstracts": 0, "pages": 0}

        all_pages = set()
        for chunk in chunks:
            all_pages.update(chunk.page_numbers)

        # Step 2: Compress
        def compression_cb(current, total):
            pct = int((current / total) * 50) if total > 0 else 0
            with _print_lock:
                progress.update(
                    task_id,
                    description=f"[yellow]Compressing [{file_idx}/{total_files}] {doc_name} ({current}/{total})",
                    completed=pct
                )

        abstracts = compression_agent.compress_batch(chunks, progress_callback=compression_cb)

        # Step 3: Embed and index
        def indexing_cb(current, total):
            pct = 50 + int((current / total) * 50) if total > 0 else 50
            with _print_lock:
                progress.update(
                    task_id,
                    description=f"[cyan]Indexing [{file_idx}/{total_files}] {doc_name} ({current}/{total})",
                    completed=pct
                )

        vector_store.add_abstracts(abstracts, progress_callback=indexing_cb)

        elapsed = time.time() - doc_start
        with _print_lock:
            progress.update(task_id, description=f"[green]✓ [{file_idx}/{total_files}] {doc_name}", completed=100)
            console.print(
                f"[green]✓ [{file_idx}/{total_files}] {doc_name} — "
                f"{len(chunks)} chunks, {len(abstracts)} abstracts, "
                f"{len(all_pages)} pages, {elapsed:.1f}s[/green]"
            )

        return {
            "name": doc_name, "error": None,
            "chunks": len(chunks), "abstracts": len(abstracts), "pages": len(all_pages)
        }

    except Exception as e:
        with _print_lock:
            progress.update(task_id, description=f"[red]✗ [{file_idx}/{total_files}] {doc_name} - {e}", completed=100)
            console.print(f"[red]✗ [{file_idx}/{total_files}] {doc_name} - {e}[/red]")
        return {"name": doc_name, "error": str(e), "chunks": 0, "abstracts": 0, "pages": 0}


def _print_summary(stats: IngestionStats, vector_store: VectorStore):
    """Print ingestion summary."""
    console.print("\n[bold green]Ingestion Complete![/bold green]\n")

    table = Table(title="Ingestion Statistics")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Documents Processed", str(len(stats.documents_processed)))
    table.add_row("Total Pages", str(stats.total_pages))
    table.add_row("Total Chunks", str(stats.total_chunks))
    table.add_row("Compressed Abstracts", str(stats.total_abstracts))
    table.add_row("Processing Time", f"{stats.processing_time_seconds:.2f}s")

    if stats.failed_documents:
        table.add_row("Failed Documents", ", ".join(stats.failed_documents))

    console.print(table)

    # Refresh index so stats are accurate
    if hasattr(vector_store, 'client'):
        vector_store.client.indices.refresh(index=vector_store.config.opensearch_index)

    vs_stats = vector_store.get_stats()
    console.print(f"\n[bold]Vector Store:[/bold] {vs_stats['total_abstracts']} abstracts indexed")
    console.print(f"[bold]Documents:[/bold] {', '.join(vs_stats['documents'])}")


@app.command()
def main(
    files: list[str] = typer.Argument(..., help="PDF filenames to ingest (up to 3)"),
    clear: bool = typer.Option(False, "--clear", "-c", help="Clear existing data before ingestion"),
    documents_dir: str = typer.Option("./documents", "--dir", help="Documents directory"),
):
    """Ingest up to 3 PDF documents in parallel."""
    docs_path = Path(documents_dir)
    if not docs_path.exists():
        console.print(f"[red]Documents directory not found: {docs_path}[/red]")
        raise typer.Exit(1)

    if len(files) > 3:
        console.print("[red]Maximum 3 files at a time. Pass up to 3 filenames.[/red]")
        raise typer.Exit(1)

    # Resolve file paths
    pdf_files = []
    for f in files:
        path = docs_path / f
        if not path.exists():
            console.print(f"[red]File not found: {path}[/red]")
            raise typer.Exit(1)
        pdf_files.append(path)

    console.print("[bold blue]Initializing CLaRa Parallel Ingestion Pipeline...[/bold blue]")

    vector_store = VectorStore()

    if clear:
        console.print("[yellow]Clearing existing vector store data...[/yellow]")
        vector_store.clear()

    # Check already-indexed documents
    already_indexed = set()
    if not clear:
        try:
            vs_stats = vector_store.get_stats()
            already_indexed = set(vs_stats.get("documents", []))
        except Exception:
            pass

    # Filter out already-indexed
    original_count = len(pdf_files)
    pdf_files = [f for f in pdf_files if f.name not in already_indexed]
    skipped = original_count - len(pdf_files)
    if skipped > 0:
        console.print(f"[blue]Skipping {skipped} already-indexed document(s)[/blue]")

    if not pdf_files:
        console.print("[green]All specified documents are already indexed. Nothing to do.[/green]")
        return

    total_files = len(pdf_files)
    console.print(f"[green]Processing {total_files} document(s) in parallel[/green]")

    stats = IngestionStats()
    stats.total_documents = total_files
    start_time = time.time()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
        transient=True
    ) as progress:

        # Create progress tasks for each file
        task_ids = {}
        for idx, pdf_path in enumerate(pdf_files, start=1):
            task_ids[pdf_path.name] = (idx, progress.add_task(
                f"[cyan]Queued [{idx}/{total_files}] {pdf_path.name}",
                total=100
            ))

        # Launch up to 3 threads — one per document
        with ThreadPoolExecutor(max_workers=min(3, total_files)) as executor:
            futures = {}
            for pdf_path in pdf_files:
                file_idx, task_id = task_ids[pdf_path.name]
                future = executor.submit(
                    _process_one_document,
                    pdf_path, file_idx, total_files, progress, task_id,
                )
                futures[future] = pdf_path.name

            # Collect results as they complete
            for future in as_completed(futures):
                result = future.result()
                if result["error"]:
                    stats.failed_documents.append(result["name"])
                else:
                    stats.documents_processed.append(result["name"])
                    stats.total_chunks += result["chunks"]
                    stats.total_abstracts += result["abstracts"]
                    stats.total_pages += result["pages"]

    stats.processing_time_seconds = time.time() - start_time
    _print_summary(stats, vector_store)


if __name__ == "__main__":
    app()
