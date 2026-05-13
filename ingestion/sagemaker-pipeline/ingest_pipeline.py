"""
Document Ingestion Pipeline for SageMaker.

Processes crawled regulatory PDFs through the full pipeline:
  1. Extract text from PDFs (PyMuPDF)
  2. Chunk text into manageable sections
  3. Compress each chunk via Bedrock LLM (compress_v2)
  4. Generate embeddings via Bedrock Titan
  5. Index into OpenSearch with hybrid search support

Usage on SageMaker:
  # From a SageMaker notebook cell:
  from ingest_pipeline import IngestionPipeline
  pipeline = IngestionPipeline(s3_bucket="ms-sos-legal-documents", s3_prefix="crawled-documents")
  stats = pipeline.run()

  # Or for a specific state/agency:
  stats = pipeline.run(states=["MS", "TN"], agency_types=["medical"])

Environment variables required:
  USE_AWS=true
  AWS_REGION=us-east-1
  OPENSEARCH_ENDPOINT=https://your-opensearch-domain.us-east-1.es.amazonaws.com
  OPENSEARCH_INDEX=ms-legal-abstracts
  BEDROCK_LLM_MODEL=mistral.mistral-large-3-675b-instruct
  BEDROCK_EMBEDDING_MODEL=amazon.titan-embed-text-v2:0
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
import traceback
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Callable

import boto3

# These imports assume SageMaker notebook has the Sagemaker Files directory in sys.path
from config import config
from models import DocumentChunk, CompressedAbstractV2, IngestionStats
from compression_agent_bedrock import BedrockCompressionAgent
from vector_store_opensearch import OpenSearchVectorStore


# ── PDF Text Extraction ─────────────────────────────────────────────────

def extract_text_from_pdf(pdf_path: str) -> list[dict]:
    """
    Extract text from a PDF, returning a list of {page_number, text} dicts.

    Uses PyMuPDF (fitz) for robust extraction. Falls back to pdfplumber
    if fitz is not available.
    """
    pages = []

    try:
        import fitz  # PyMuPDF
        doc = fitz.open(pdf_path)
        for page_num in range(len(doc)):
            page = doc[page_num]
            text = page.get_text("text")
            if text.strip():
                pages.append({"page_number": page_num + 1, "text": text})
        doc.close()
    except ImportError:
        try:
            import pdfplumber
            with pdfplumber.open(pdf_path) as pdf:
                for i, page in enumerate(pdf.pages):
                    text = page.extract_text() or ""
                    if text.strip():
                        pages.append({"page_number": i + 1, "text": text})
        except ImportError:
            raise ImportError(
                "Either PyMuPDF (fitz) or pdfplumber is required. "
                "Install with: pip install PyMuPDF  or  pip install pdfplumber"
            )

    return pages


# ── Text Chunking ────────────────────────────────────────────────────────

def chunk_document(
    pages: list[dict],
    document_name: str,
    document_path: str,
    chunk_size: int = 2000,
    chunk_overlap: int = 200,
    state: str = "",
    agency_type: str = "",
) -> list[DocumentChunk]:
    """
    Split extracted pages into overlapping chunks suitable for compression.

    Strategy:
      - Concatenate all pages into a single text with page markers
      - Split on section boundaries (Rule X.X, Section X, Chapter X) when possible
      - Fall back to size-based splitting with overlap
    """
    if not pages:
        return []

    # Build full text with page tracking
    full_text = ""
    page_map: list[tuple[int, int, int]] = []  # (start_char, end_char, page_num)

    for page in pages:
        start = len(full_text)
        full_text += page["text"] + "\n\n"
        end = len(full_text)
        page_map.append((start, end, page["page_number"]))

    # Try to split on section boundaries first
    section_pattern = re.compile(
        r'\n(?=(?:Rule|Section|§|Chapter|Part|Article|Subchapter|RULE|SECTION|CHAPTER)\s+[\d§])',
        re.MULTILINE,
    )
    section_splits = list(section_pattern.finditer(full_text))

    chunks: list[DocumentChunk] = []

    if section_splits and len(section_splits) >= 2:
        # Section-based splitting
        boundaries = [0] + [m.start() for m in section_splits] + [len(full_text)]
        raw_sections = []
        for i in range(len(boundaries) - 1):
            section_text = full_text[boundaries[i]:boundaries[i + 1]].strip()
            if section_text:
                raw_sections.append((boundaries[i], boundaries[i + 1], section_text))

        # Merge very small sections with next, split very large ones
        merged_sections = []
        buffer_start = None
        buffer_text = ""
        for start, end, text in raw_sections:
            if buffer_start is None:
                buffer_start = start
                buffer_text = text
            elif len(buffer_text) + len(text) < chunk_size:
                buffer_text += "\n\n" + text
            else:
                merged_sections.append((buffer_start, buffer_text))
                buffer_start = start
                buffer_text = text
        if buffer_text:
            merged_sections.append((buffer_start, buffer_text))

        for idx, (char_start, text) in enumerate(merged_sections):
            # If still too large, do size-based sub-splitting
            if len(text) > chunk_size * 2:
                sub_chunks = _size_split(text, chunk_size, chunk_overlap)
                for sub_idx, sub_text in enumerate(sub_chunks):
                    page_nums = _get_pages_for_range(
                        char_start, char_start + len(sub_text), page_map
                    )
                    section_title = _detect_section_title(sub_text)
                    chunks.append(DocumentChunk(
                        chunk_id=f"{document_name}_{idx}_{sub_idx}",
                        document_name=document_name,
                        document_path=document_path,
                        page_numbers=page_nums,
                        section_title=section_title,
                        raw_text=sub_text,
                        chunk_index=len(chunks),
                        total_chunks=0,  # filled later
                        state=state,
                        agency_type=agency_type,
                    ))
            else:
                page_nums = _get_pages_for_range(
                    char_start, char_start + len(text), page_map
                )
                section_title = _detect_section_title(text)
                chunks.append(DocumentChunk(
                    chunk_id=f"{document_name}_{idx}",
                    document_name=document_name,
                    document_path=document_path,
                    page_numbers=page_nums,
                    section_title=section_title,
                    raw_text=text,
                    chunk_index=len(chunks),
                    total_chunks=0,
                    state=state,
                    agency_type=agency_type,
                ))
    else:
        # Size-based splitting
        sub_chunks = _size_split(full_text, chunk_size, chunk_overlap)
        for idx, text in enumerate(sub_chunks):
            page_nums = _get_pages_for_range(0, len(text), page_map)
            section_title = _detect_section_title(text)
            chunks.append(DocumentChunk(
                chunk_id=f"{document_name}_{idx}",
                document_name=document_name,
                document_path=document_path,
                page_numbers=page_nums,
                section_title=section_title,
                raw_text=text,
                chunk_index=idx,
                total_chunks=0,
                state=state,
                agency_type=agency_type,
            ))

    # Fill total_chunks
    for chunk in chunks:
        chunk.total_chunks = len(chunks)

    return chunks


def _size_split(text: str, chunk_size: int, overlap: int) -> list[str]:
    """Split text into overlapping chunks by character count."""
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        # Try to break at a paragraph or sentence boundary
        if end < len(text):
            # Look for paragraph break
            para_break = text.rfind("\n\n", start + chunk_size // 2, end + 200)
            if para_break > start:
                end = para_break
            else:
                # Look for sentence break
                sent_break = text.rfind(". ", start + chunk_size // 2, end + 100)
                if sent_break > start:
                    end = sent_break + 1

        chunk_text = text[start:end].strip()
        if chunk_text:
            chunks.append(chunk_text)
        start = max(start + 1, end - overlap)

    return chunks


def _get_pages_for_range(
    char_start: int, char_end: int, page_map: list[tuple[int, int, int]]
) -> list[int]:
    """Determine which page numbers a character range spans."""
    pages = []
    for p_start, p_end, page_num in page_map:
        if char_start < p_end and char_end > p_start:
            pages.append(page_num)
    return pages or [1]


def _detect_section_title(text: str) -> str | None:
    """Extract the section/rule/chapter identifier from the start of text."""
    match = re.match(
        r'((?:Rule|Section|§|Chapter|Part|Article)\s+[\d§][\w.\-]*(?:\s+[\w\-]+)?)',
        text.strip(),
        re.IGNORECASE,
    )
    return match.group(1).strip() if match else None


# ── S3 Helpers ───────────────────────────────────────────────────────────

def list_s3_pdfs(
    s3_client,
    bucket: str,
    prefix: str,
    states: list[str] | None = None,
    agency_types: list[str] | None = None,
) -> list[dict]:
    """
    List PDF files in S3 under the crawled-documents prefix.

    Expected S3 structure: {prefix}/{STATE}/{agency_type}/{filename}.pdf
    """
    pdfs = []
    paginator = s3_client.get_paginator("list_objects_v2")

    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            if not key.lower().endswith(".pdf"):
                continue

            # Parse state and agency from key
            parts = key.replace(prefix, "").strip("/").split("/")
            if len(parts) < 3:
                continue

            state = parts[0].upper()
            agency_type = parts[1].lower()

            if states and state not in [s.upper() for s in states]:
                continue
            if agency_types and agency_type not in [a.lower() for a in agency_types]:
                continue

            pdfs.append({
                "key": key,
                "state": state,
                "agency_type": agency_type,
                "filename": parts[-1],
                "size": obj["Size"],
            })

    return pdfs


def download_from_s3(s3_client, bucket: str, key: str, local_path: str):
    """Download a file from S3 to a local path."""
    Path(local_path).parent.mkdir(parents=True, exist_ok=True)
    s3_client.download_file(bucket, key, local_path)


# ── Agency Name Lookup ───────────────────────────────────────────────────

AGENCY_NAMES = {
    ("MS", "medical"): "Mississippi State Board of Medical Licensure",
    ("MS", "real_estate"): "Mississippi Real Estate Commission",
    ("MS", "dental"): "Mississippi State Board of Dental Examiners",
    ("TN", "medical"): "Tennessee Board of Medical Examiners",
    ("TN", "real_estate"): "Tennessee Real Estate Commission",
    ("TN", "dental"): "Tennessee Board of Dentistry",
    ("AL", "medical"): "Alabama Board of Medical Examiners",
    ("AL", "real_estate"): "Alabama Real Estate Commission",
    ("AL", "dental"): "Alabama Board of Dental Examiners",
    ("LA", "medical"): "Louisiana State Board of Medical Examiners",
    ("LA", "real_estate"): "Louisiana Real Estate Commission",
    ("LA", "dental"): "Louisiana State Board of Dentistry",
    ("AR", "medical"): "Arkansas State Medical Board",
    ("AR", "real_estate"): "Arkansas Real Estate Commission",
    ("AR", "dental"): "Arkansas State Board of Dental Examiners",
    ("GA", "medical"): "Georgia Composite Medical Board",
    ("GA", "real_estate"): "Georgia Real Estate Commission",
    ("GA", "dental"): "Georgia Board of Dentistry",
    ("TX", "medical"): "Texas Medical Board",
    ("TX", "real_estate"): "Texas Real Estate Commission",
    ("TX", "dental"): "Texas State Board of Dental Examiners",
}


# ── Main Pipeline ────────────────────────────────────────────────────────

@dataclass
class PipelineConfig:
    """Configuration for the ingestion pipeline."""
    s3_bucket: str = "ms-sos-legal-documents"
    s3_prefix: str = "crawled-documents"
    local_tmp_dir: str = "/tmp/sos-ingest"
    chunk_size: int = 2000
    chunk_overlap: int = 200
    batch_size: int = 20
    retry_delay: float = 2.0
    max_retries: int = 3


class IngestionPipeline:
    """
    End-to-end ingestion pipeline for regulatory documents.

    Designed to run on SageMaker with Bedrock + OpenSearch access.
    """

    def __init__(
        self,
        s3_bucket: str | None = None,
        s3_prefix: str | None = None,
        local_dir: str | None = None,
        pipeline_config: PipelineConfig | None = None,
    ):
        self.config = pipeline_config or PipelineConfig()
        if s3_bucket:
            self.config.s3_bucket = s3_bucket
        if s3_prefix:
            self.config.s3_prefix = s3_prefix
        if local_dir:
            self.config.local_tmp_dir = local_dir

        self.s3 = boto3.client("s3")
        self.compressor = BedrockCompressionAgent()
        self.vector_store = OpenSearchVectorStore()

        self.stats = IngestionStats()
        self._start_time = None

    def run(
        self,
        states: list[str] | None = None,
        agency_types: list[str] | None = None,
        progress_callback: Callable[[str], None] | None = None,
    ) -> IngestionStats:
        """
        Run the full ingestion pipeline.

        Args:
            states: Filter to specific states (e.g., ["MS", "TN"]).
            agency_types: Filter to specific agency types (e.g., ["medical"]).
            progress_callback: Called with status messages during processing.
        """
        self._start_time = time.time()
        self.stats = IngestionStats()

        def log(msg: str):
            print(msg)
            if progress_callback:
                progress_callback(msg)

        # Step 1: List documents in S3
        log(f"Listing PDFs in s3://{self.config.s3_bucket}/{self.config.s3_prefix}/...")
        pdfs = list_s3_pdfs(
            self.s3, self.config.s3_bucket, self.config.s3_prefix,
            states=states, agency_types=agency_types,
        )
        log(f"Found {len(pdfs)} PDFs to process")
        self.stats.total_documents = len(pdfs)

        if not pdfs:
            log("No documents found. Check S3 bucket/prefix and filters.")
            return self.stats

        # Step 2: Process each document
        for idx, pdf_info in enumerate(pdfs, 1):
            doc_name = pdf_info["filename"]
            state = pdf_info["state"]
            agency_type = pdf_info["agency_type"]
            agency_name = AGENCY_NAMES.get((state, agency_type), f"{state} {agency_type}")

            log(f"\n[{idx}/{len(pdfs)}] {state}/{agency_type}/{doc_name}")

            try:
                abstracts = self._process_document(pdf_info, log)
                if abstracts:
                    # Step 3: Index into OpenSearch in batches
                    self._index_abstracts(abstracts, log)
                    self.stats.documents_processed.append(doc_name)
                    self.stats.total_abstracts += len(abstracts)
                else:
                    log(f"  No abstracts generated — skipping")
            except Exception as exc:
                log(f"  FAILED: {exc}")
                traceback.print_exc()
                self.stats.failed_documents.append(f"{state}/{agency_type}/{doc_name}: {exc}")

        self.stats.processing_time_seconds = time.time() - self._start_time
        log(f"\n{'='*60}")
        log(f"Ingestion complete in {self.stats.processing_time_seconds:.1f}s")
        log(f"  Documents processed: {len(self.stats.documents_processed)}/{self.stats.total_documents}")
        log(f"  Total chunks: {self.stats.total_chunks}")
        log(f"  Total abstracts indexed: {self.stats.total_abstracts}")
        log(f"  Failed: {len(self.stats.failed_documents)}")

        return self.stats

    def _process_document(
        self, pdf_info: dict, log: Callable[[str], None]
    ) -> list[CompressedAbstractV2]:
        """Download, extract, chunk, and compress a single PDF."""
        state = pdf_info["state"]
        agency_type = pdf_info["agency_type"]
        agency_name = AGENCY_NAMES.get((state, agency_type), "")
        doc_name = pdf_info["filename"]

        # Download from S3
        local_path = os.path.join(
            self.config.local_tmp_dir, state, agency_type, doc_name
        )
        download_from_s3(self.s3, self.config.s3_bucket, pdf_info["key"], local_path)
        log(f"  Downloaded ({pdf_info['size'] // 1024}KB)")

        # Extract text
        pages = extract_text_from_pdf(local_path)
        if not pages:
            log(f"  No text extracted (scanned PDF?)")
            return []

        total_pages = len(pages)
        self.stats.total_pages += total_pages
        log(f"  Extracted {total_pages} pages of text")

        # Chunk
        chunks = chunk_document(
            pages, doc_name, pdf_info["key"],
            chunk_size=self.config.chunk_size,
            chunk_overlap=self.config.chunk_overlap,
            state=state,
            agency_type=agency_type,
        )
        self.stats.total_chunks += len(chunks)
        log(f"  Split into {len(chunks)} chunks")

        # Compress each chunk with retry logic
        abstracts: list[CompressedAbstractV2] = []
        for i, chunk in enumerate(chunks):
            for attempt in range(self.config.max_retries):
                try:
                    abstract = self.compressor.compress_v2(
                        chunk,
                        state=state,
                        agency_type=agency_type,
                        agency_name=agency_name,
                    )
                    abstracts.append(abstract)
                    break
                except Exception as exc:
                    if attempt < self.config.max_retries - 1:
                        wait = self.config.retry_delay * (attempt + 1)
                        time.sleep(wait)
                    else:
                        log(f"  Chunk {i+1}/{len(chunks)} failed after {self.config.max_retries} retries: {exc}")

            if (i + 1) % 10 == 0:
                log(f"  Compressed {i+1}/{len(chunks)} chunks")

        log(f"  Compressed {len(abstracts)}/{len(chunks)} chunks successfully")

        # Cleanup local file
        try:
            os.remove(local_path)
        except OSError:
            pass

        return abstracts

    def _index_abstracts(
        self, abstracts: list[CompressedAbstractV2], log: Callable[[str], None]
    ):
        """Index abstracts into OpenSearch in batches."""
        batch_size = self.config.batch_size
        total = len(abstracts)

        for i in range(0, total, batch_size):
            batch = abstracts[i:i + batch_size]
            for attempt in range(self.config.max_retries):
                try:
                    self.vector_store.add_abstracts(batch)
                    break
                except Exception as exc:
                    if attempt < self.config.max_retries - 1:
                        wait = self.config.retry_delay * (attempt + 1)
                        log(f"  Index batch retry ({attempt+1}): {exc}")
                        time.sleep(wait)
                    else:
                        raise

        log(f"  Indexed {total} abstracts into OpenSearch")


# ── Local Mode (for testing without S3) ──────────────────────────────────

class LocalIngestionPipeline(IngestionPipeline):
    """
    Variant that reads PDFs from a local directory instead of S3.

    Useful for testing on a dev machine before deploying to SageMaker.

    Usage:
        pipeline = LocalIngestionPipeline(local_dir="./crawled_documents")
        stats = pipeline.run(states=["MS"])
    """

    def __init__(self, local_dir: str = "./crawled_documents", **kwargs):
        self.local_root = Path(local_dir)
        # Skip S3 client init — override run() to use local files
        self.compressor = BedrockCompressionAgent()
        self.vector_store = OpenSearchVectorStore()
        self.config = PipelineConfig()
        self.stats = IngestionStats()
        self._start_time = None

    def run(
        self,
        states: list[str] | None = None,
        agency_types: list[str] | None = None,
        progress_callback: Callable[[str], None] | None = None,
    ) -> IngestionStats:
        self._start_time = time.time()
        self.stats = IngestionStats()

        def log(msg: str):
            print(msg)
            if progress_callback:
                progress_callback(msg)

        # List local PDFs
        pdfs = []
        for pdf_path in sorted(self.local_root.rglob("*.pdf")):
            parts = pdf_path.relative_to(self.local_root).parts
            if len(parts) < 3:
                continue
            state = parts[0].upper()
            agency_type = parts[1].lower()

            if states and state not in [s.upper() for s in states]:
                continue
            if agency_types and agency_type not in [a.lower() for a in agency_types]:
                continue

            pdfs.append({
                "path": str(pdf_path),
                "key": str(pdf_path),
                "state": state,
                "agency_type": agency_type,
                "filename": parts[-1],
                "size": pdf_path.stat().st_size,
            })

        log(f"Found {len(pdfs)} local PDFs to process")
        self.stats.total_documents = len(pdfs)

        for idx, pdf_info in enumerate(pdfs, 1):
            doc_name = pdf_info["filename"]
            state = pdf_info["state"]
            agency_type = pdf_info["agency_type"]
            agency_name = AGENCY_NAMES.get((state, agency_type), "")

            log(f"\n[{idx}/{len(pdfs)}] {state}/{agency_type}/{doc_name}")

            try:
                abstracts = self._process_local_document(pdf_info, log)
                if abstracts:
                    self._index_abstracts(abstracts, log)
                    self.stats.documents_processed.append(doc_name)
                    self.stats.total_abstracts += len(abstracts)
            except Exception as exc:
                log(f"  FAILED: {exc}")
                traceback.print_exc()
                self.stats.failed_documents.append(f"{state}/{agency_type}/{doc_name}: {exc}")

        self.stats.processing_time_seconds = time.time() - self._start_time
        log(f"\n{'='*60}")
        log(f"Ingestion complete in {self.stats.processing_time_seconds:.1f}s")
        log(f"  Documents: {len(self.stats.documents_processed)}/{self.stats.total_documents}")
        log(f"  Chunks: {self.stats.total_chunks}")
        log(f"  Abstracts: {self.stats.total_abstracts}")
        log(f"  Failed: {len(self.stats.failed_documents)}")

        return self.stats

    def _process_local_document(
        self, pdf_info: dict, log: Callable[[str], None]
    ) -> list[CompressedAbstractV2]:
        """Process a local PDF file."""
        state = pdf_info["state"]
        agency_type = pdf_info["agency_type"]
        agency_name = AGENCY_NAMES.get((state, agency_type), "")
        doc_name = pdf_info["filename"]
        local_path = pdf_info["path"]

        log(f"  Reading ({pdf_info['size'] // 1024}KB)")

        pages = extract_text_from_pdf(local_path)
        if not pages:
            log(f"  No text extracted (scanned PDF?)")
            return []

        self.stats.total_pages += len(pages)
        log(f"  Extracted {len(pages)} pages")

        chunks = chunk_document(
            pages, doc_name, local_path,
            chunk_size=self.config.chunk_size,
            chunk_overlap=self.config.chunk_overlap,
            state=state, agency_type=agency_type,
        )
        self.stats.total_chunks += len(chunks)
        log(f"  Split into {len(chunks)} chunks")

        abstracts: list[CompressedAbstractV2] = []
        for i, chunk in enumerate(chunks):
            for attempt in range(self.config.max_retries):
                try:
                    abstract = self.compressor.compress_v2(
                        chunk, state=state,
                        agency_type=agency_type, agency_name=agency_name,
                    )
                    abstracts.append(abstract)
                    break
                except Exception as exc:
                    if attempt < self.config.max_retries - 1:
                        time.sleep(self.config.retry_delay * (attempt + 1))
                    else:
                        log(f"  Chunk {i+1}/{len(chunks)} failed: {exc}")

            if (i + 1) % 10 == 0:
                log(f"  Compressed {i+1}/{len(chunks)} chunks")

        log(f"  Compressed {len(abstracts)}/{len(chunks)} chunks")
        return abstracts


# ── CLI entrypoint ───────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Ingest crawled regulatory PDFs into OpenSearch")
    parser.add_argument("--state", action="append", dest="states", help="Filter by state")
    parser.add_argument("--agency", action="append", dest="agency_types", help="Filter by agency type")
    parser.add_argument("--local", default=None, help="Use local directory instead of S3")
    parser.add_argument("--s3-bucket", default="ms-sos-legal-documents")
    parser.add_argument("--s3-prefix", default="crawled-documents")
    parser.add_argument("--chunk-size", type=int, default=2000)
    parser.add_argument("--batch-size", type=int, default=20)

    args = parser.parse_args()

    cfg = PipelineConfig(
        s3_bucket=args.s3_bucket,
        s3_prefix=args.s3_prefix,
        chunk_size=args.chunk_size,
        batch_size=args.batch_size,
    )

    if args.local:
        pipeline = LocalIngestionPipeline(local_dir=args.local)
    else:
        pipeline = IngestionPipeline(pipeline_config=cfg)

    stats = pipeline.run(states=args.states, agency_types=args.agency_types)
    print(f"\nFinal stats: {stats.model_dump_json(indent=2)}")
