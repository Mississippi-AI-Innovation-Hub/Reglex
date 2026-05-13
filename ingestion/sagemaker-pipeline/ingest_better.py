#!/usr/bin/env python3
"""
Document Ingestion Pipeline for the CLaRa Legal Analysis System.

This script implements the CLaRa-inspired ingestion process:
1. Load PDFs from the documents/ folder
2. Split into manageable chunks while preserving page numbers
3. Compress each chunk using the LLM (CLaRa "latent" step)
4. Embed and store compressed abstracts in ChromaDB

Usage:
    python ingest.py                    # Ingest all documents
    python ingest.py --clear            # Clear existing data first
    python ingest.py --document FILE    # Ingest specific file
"""
import logging
import time
import hashlib
import os
from pathlib import Path
from typing import Generator, Optional

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.table import Table
from pypdf import PdfReader

from config import config
from models import DocumentChunk, IngestionStats

logging.getLogger("pypdf").setLevel(logging.ERROR)

# Import modules based on configuration
# Compression Agent: Use Bedrock if AWS is configured, otherwise local
if config.aws:
    from compression_agent_bedrock import BedrockCompressionAgent as CompressionAgent
else:
    from compression_agent import CompressionAgent

# Vector Store: Use OpenSearch if endpoint is configured, otherwise local ChromaDB
if config.aws and config.aws.opensearch_endpoint:
    from vector_store_opensearch import OpenSearchVectorStore as VectorStore
else:
    from vector_store import VectorStore

console = Console()
app = typer.Typer(
    help="CLaRa Legal Document Ingestion Pipeline",
    invoke_without_command=True,
    no_args_is_help=False
)


class DocumentLoader:
    """Loads and chunks PDF documents while preserving metadata."""

    def __init__(self, chunk_size: int = 2000, chunk_overlap: int = 200):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def load_pdf(self, pdf_path: Path) -> Generator[DocumentChunk, None, None]:
        """
        Load a PDF and yield document chunks with page tracking.

        Args:
            pdf_path: Path to the PDF file

        Yields:
            DocumentChunk objects with raw text and metadata
        """
        reader = PdfReader(pdf_path)
        document_name = pdf_path.name

        # Extract text with page numbers
        pages_text = []
        for page_num, page in enumerate(reader.pages, start=1):
            text = page.extract_text() or ""
            if text.strip():
                pages_text.append((page_num, text))

        if not pages_text:
            console.print(f"[yellow]Warning: No text extracted from {document_name}[/yellow]")
            return

        # Combine all text for chunking, but track page boundaries
        combined_text = ""
        page_boundaries = []  # (start_char, end_char, page_num)

        for page_num, text in pages_text:
            start = len(combined_text)
            combined_text += text + "\n\n"
            end = len(combined_text)
            page_boundaries.append((start, end, page_num))

        # Create chunks with overlap
        chunks = self._create_chunks(combined_text)
        total_chunks = len(chunks)

        for chunk_idx, (start, end, text) in enumerate(chunks):
            # Determine which pages this chunk spans
            chunk_pages = self._get_pages_for_range(start, end, page_boundaries)

            # Try to detect section title (first line if it looks like a header)
            section_title = self._detect_section_title(text)

            # Generate chunk ID
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
        """
        Split text into overlapping chunks.

        Returns list of (start_char, end_char, text) tuples.
        """
        chunks = []
        start = 0

        while start < len(text):
            end = start + self.chunk_size

            # Try to break at paragraph or sentence boundary
            if end < len(text):
                # Look for paragraph break
                para_break = text.rfind("\n\n", start, end)
                if para_break > start + self.chunk_size // 2:
                    end = para_break + 2
                else:
                    # Look for sentence break
                    for punct in [". ", ".\n", "? ", "?\n", "! ", "!\n"]:
                        sent_break = text.rfind(punct, start, end)
                        if sent_break > start + self.chunk_size // 2:
                            end = sent_break + len(punct)
                            break

            chunk_text = text[start:end].strip()
            if chunk_text:
                chunks.append((start, end, chunk_text))

            # Move start with overlap
            start = end - self.chunk_overlap
            if start >= len(text) - self.chunk_overlap:
                break

        return chunks

    def _get_pages_for_range(
        self,
        start: int,
        end: int,
        page_boundaries: list[tuple[int, int, int]]
    ) -> list[int]:
        """Determine which pages a character range spans."""
        pages = []
        for page_start, page_end, page_num in page_boundaries:
            # Check if ranges overlap
            if start < page_end and end > page_start:
                pages.append(page_num)
        return pages or [1]  # Default to page 1 if no overlap found

    def _detect_section_title(self, text: str) -> Optional[str]:
        """Try to detect if the chunk starts with a section title."""
        lines = text.strip().split("\n")
        if not lines:
            return None

        first_line = lines[0].strip()

        # Heuristics for section titles
        # 1. Short lines (likely headers)
        # 2. Lines starting with "Section", "Chapter", "Part", numbers
        # 3. Lines in ALL CAPS

        if len(first_line) < 100:
            if any(first_line.upper().startswith(prefix) for prefix in
                   ["SECTION", "CHAPTER", "PART", "ARTICLE", "RULE", "REGULATION"]):
                return first_line

            # Check for section numbers like "1.1", "§ 75-1-101"
            if first_line and (first_line[0].isdigit() or first_line.startswith("§")):
                # Likely a section number
                return first_line[:80]  # Truncate long titles

            # Check for ALL CAPS (common for headers)
            if first_line.isupper() and len(first_line) > 5:
                return first_line

        return None


def ingest_documents(
    documents_dir: Path,
    clear_existing: bool = False,
    specific_document: Optional[str] = None
) -> IngestionStats:
    """
    Serial ingestion pipeline — processes one document at a time with all resources.

    Args:
        documents_dir: Directory containing PDF documents
        clear_existing: Whether to clear existing vector store data
        specific_document: Optional specific document to ingest

    Returns:
        IngestionStats with processing details
    """
    stats = IngestionStats()

    # Initialize components once — reused across all documents
    console.print("[bold blue]Initializing CLaRa Ingestion Pipeline...[/bold blue]")

    loader = DocumentLoader(
        chunk_size=config.documents.chunk_size,
        chunk_overlap=config.documents.chunk_overlap
    )
    compression_agent = CompressionAgent()
    vector_store = VectorStore()

    if clear_existing:
        console.print("[yellow]Clearing existing vector store data...[/yellow]")
        vector_store.clear()

    # Find documents to process
    if specific_document:
        pdf_files = [documents_dir / specific_document]
        if not pdf_files[0].exists():
            console.print(f"[red]Document not found: {specific_document}[/red]")
            return stats
    else:
        pdf_files = sorted(documents_dir.glob("*.pdf"))

    if not pdf_files:
        console.print(f"[yellow]No PDF files found in {documents_dir}[/yellow]")
        return stats

    # Check which documents are already indexed — skip them
    # (only when bulk-processing, not when a specific document is requested)
    already_indexed = set()
    if not clear_existing and not specific_document:
        try:
            vs_stats = vector_store.get_stats()
            already_indexed = set(vs_stats.get("documents", []))
            if already_indexed:
                console.print(f"[blue]Already indexed: {len(already_indexed)} document(s)[/blue]")
        except Exception:
            pass  # If stats fail, just process everything

    # Filter out already-indexed documents
    original_count = len(pdf_files)
    pdf_files = [f for f in pdf_files if f.name not in already_indexed]
    skipped = original_count - len(pdf_files)
    if skipped > 0:
        console.print(f"[blue]Skipping {skipped} already-indexed document(s)[/blue]")

    if not pdf_files:
        console.print(f"[green]All {original_count} documents are already indexed. Nothing to do.[/green]")
        _print_summary(stats, vector_store)
        return stats

    total_files = len(pdf_files)
    stats.total_documents = total_files
    console.print(f"[green]Found {total_files} PDF document(s) to process[/green]")

    start_time = time.time()

    # Process each document serially — all resources dedicated to one file at a time
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
        transient=True
    ) as progress:

        for file_idx, pdf_path in enumerate(pdf_files, start=1):
            doc_name = pdf_path.name
            doc_start = time.time()

            # Progress task for this document
            task_id = progress.add_task(
                f"[yellow]Loading [{file_idx}/{total_files}] {doc_name}...",
                total=100
            )

            try:
                # Step 1: Load and chunk
                chunks = list(loader.load_pdf(pdf_path))
                if not chunks:
                    progress.update(task_id, description=f"[yellow]⚠ [{file_idx}/{total_files}] {doc_name} - no text extracted", completed=100)
                    console.print(f"[yellow]⚠ [{file_idx}/{total_files}] {doc_name} - no text extracted[/yellow]")
                    continue

                all_pages = set()
                for chunk in chunks:
                    all_pages.update(chunk.page_numbers)

                # Step 2: Compress all chunks
                def compression_callback(current, total):
                    pct = int((current / total) * 50) if total > 0 else 0  # 0-50% for compression
                    progress.update(
                        task_id,
                        description=f"[yellow]Compressing [{file_idx}/{total_files}] {doc_name} ({current}/{total} chunks)",
                        completed=pct
                    )

                abstracts = compression_agent.compress_batch(chunks, progress_callback=compression_callback)

                # Step 3: Embed and index
                def indexing_callback(current, total):
                    pct = 50 + int((current / total) * 50) if total > 0 else 50  # 50-100% for indexing
                    progress.update(
                        task_id,
                        description=f"[cyan]Indexing [{file_idx}/{total_files}] {doc_name} ({current}/{total} abstracts)",
                        completed=pct
                    )

                vector_store.add_abstracts(abstracts, progress_callback=indexing_callback)

                # Done
                elapsed = time.time() - doc_start
                progress.update(task_id, description=f"[green]✓ [{file_idx}/{total_files}] {doc_name}", completed=100)
                console.print(
                    f"[green]✓ [{file_idx}/{total_files}] {doc_name} — "
                    f"{len(chunks)} chunks, {len(abstracts)} abstracts, "
                    f"{len(all_pages)} pages, {elapsed:.1f}s[/green]"
                )

                stats.documents_processed.append(doc_name)
                stats.total_chunks += len(chunks)
                stats.total_abstracts += len(abstracts)
                stats.total_pages += len(all_pages)

            except Exception as e:
                progress.update(task_id, description=f"[red]✗ [{file_idx}/{total_files}] {doc_name} - {e}", completed=100)
                console.print(f"[red]✗ [{file_idx}/{total_files}] {doc_name} - {e}[/red]")
                stats.failed_documents.append(doc_name)

    stats.processing_time_seconds = time.time() - start_time

    # Print summary
    _print_summary(stats, vector_store)

    return stats


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

    # Refresh index so stats reflect all newly indexed documents
    if hasattr(vector_store, 'client'):
        vector_store.client.indices.refresh(index=vector_store.config.opensearch_index)
    
    # Vector store stats
    vs_stats = vector_store.get_stats()
    console.print(f"\n[bold]Vector Store:[/bold] {vs_stats['total_abstracts']} abstracts indexed")
    console.print(f"[bold]Documents:[/bold] {', '.join(vs_stats['documents'])}")


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    clear: bool = typer.Option(False, "--clear", "-c", help="Clear existing data before ingestion"),
    document: Optional[str] = typer.Option(None, "--document", "-d", help="Specific document to ingest"),
    documents_dir: Optional[str] = typer.Option(None, "--dir", help="Documents directory (default: ./documents)")
):
    """Ingest legal documents into the CLaRa system. Use subcommands for other operations."""
    # If a subcommand was invoked, don't run the default ingestion
    if ctx.invoked_subcommand is not None:
        return
    
    # Default behavior: run ingestion
    docs_path = Path(documents_dir) if documents_dir else config.documents.documents_dir

    if not docs_path.exists():
        console.print(f"[red]Documents directory not found: {docs_path}[/red]")
        console.print("[yellow]Creating directory...[/yellow]")
        docs_path.mkdir(parents=True, exist_ok=True)
        console.print(f"[green]Created {docs_path}. Please add PDF documents and run again.[/green]")
        raise typer.Exit(1)

    ingest_documents(docs_path, clear_existing=clear, specific_document=document)


@app.command()
def stats():
    """Show vector store statistics."""
    vector_store = VectorStore()
    vs_stats = vector_store.get_stats()

    table = Table(title="Vector Store Statistics")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Total Abstracts", str(vs_stats["total_abstracts"]))
    table.add_row("Unique Documents", str(vs_stats["unique_documents"]))
    # OpenSearch uses index_name; ChromaDB used collection_name
    table.add_row("Index / Collection", vs_stats.get("index_name") or vs_stats.get("collection_name", "N/A"))
    table.add_row("Embedding Model", vs_stats.get("embedding_model", config.aws.bedrock_embedding_model if config.aws else "N/A"))

    console.print(table)

    if vs_stats["documents"]:
        console.print("\n[bold]Indexed Documents:[/bold]")
        for doc in vs_stats["documents"]:
            console.print(f"  - {doc}")


@app.command()
def clear():
    """Clear all data from the vector store."""
    if typer.confirm("Are you sure you want to clear all indexed data?"):
        vector_store = VectorStore()
        vector_store.clear()
        console.print("[green]Vector store cleared successfully.[/green]")


if __name__ == "__main__":
    app()
