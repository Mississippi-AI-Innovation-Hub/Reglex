"""
V2 Ingestion Pipeline — dual-layer document + page indexing.

Runs locally using AWS SSO credentials. Processes PDFs from S3:
  1. Download PDF from S3
  2. Extract text from all pages (PyMuPDF)
  3. Scanned pages with no text → Textract OCR
  4. Table pages → Textract table extraction → clean structured text
  5. All pages: Mistral text extraction (structured fields)
  6. All pages: Titan text embedding
  7. Index document record (full text) + page records into OpenSearch

Usage:
    python pipeline.py --index ms-phase1-legal \\
        --s3-bucket ms-sos-legal-documents \\
        --s3-prefix source-documents

    # Resume after credential expiry:
    python pipeline.py --index ms-phase1-legal --resume
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path

from aws_session import AWSSession, SSOExpiredError
from extractors import (
    extract_pages,
    render_page_image,
    is_table_page,
    is_low_value_page,
    call_mistral_text,
    call_mistral_batch,
    textract_ocr,
    textract_extract_tables,
    format_tables_as_text,
    create_embedding_text,
    get_text_embedding,
    safe_date,
)
from index_manager import IndexManager, PHASE1_INDEX, PHASE2_INDEX
from lease import LeaseManager, default_session_id
from models import IngestionProgress

# ── Cost tracking (approximate Bedrock/Textract pricing) ───────────────
def _sanitize_fees(fee_amounts):
    """
    Clean fee_amounts from LLM output to ensure OpenSearch compatibility.

    The LLM sometimes returns strings like "Up to" for statutory_cap
    or "varies" for amount. These must be floats or null.
    """
    if not fee_amounts or not isinstance(fee_amounts, list):
        return []

    cleaned = []
    for fee in fee_amounts:
        if not isinstance(fee, dict):
            continue
        try:
            amount = fee.get("amount")
            if isinstance(amount, str):
                # Try to extract a number from strings like "$150" or "150.00"
                import re
                nums = re.findall(r'[\d,]+\.?\d*', amount)
                amount = float(nums[0].replace(",", "")) if nums else None
            elif amount is not None:
                amount = float(amount)

            if amount is None or amount <= 0:
                continue

            cap = fee.get("statutory_cap")
            if isinstance(cap, str):
                import re
                nums = re.findall(r'[\d,]+\.?\d*', cap)
                cap = float(nums[0].replace(",", "")) if nums else None
            elif cap is not None:
                try:
                    cap = float(cap)
                except (ValueError, TypeError):
                    cap = None

            cleaned.append({
                "amount": amount,
                "fee_type": str(fee.get("fee_type", "other")),
                "description": str(fee.get("description", "")),
                "statutory_cap": cap,
            })
        except (ValueError, TypeError):
            continue

    return cleaned


COST_MISTRAL_TEXT_PER_CALL = 0.005    # ~2K input + 500 output avg
COST_MISTRAL_BATCH_PER_CALL = 0.012  # ~6K input + 1.5K output for 3 pages
COST_TEXTRACT_OCR_PER_PAGE = 0.0015  # detect_document_text
COST_TEXTRACT_TABLE_PER_PAGE = 0.015 # analyze_document with TABLES
COST_EMBEDDING_PER_CALL = 0.0001
BATCH_SIZE = 3  # pages per Mistral call

# ── Config ──────────────────────────────────────────────────────────────
DEFAULT_LLM_MODEL = "mistral.mistral-large-3-675b-instruct"
DEFAULT_EMBEDDING_MODEL = "amazon.titan-embed-text-v2:0"
def _progress_file(index_name):
    """Per-index progress file to avoid collision between Phase 1 and Phase 2."""
    return "ingestion_progress_%s.json" % index_name
CHECK_CREDS_EVERY_N_DOCS = 10
LOCAL_TMP_DIR = "/tmp/sos-ingest-v2"


class IngestionPipeline:
    """
    V2 ingestion pipeline with dual-layer indexing.

    Processes PDFs from S3 into OpenSearch with:
    - Document-level records (full text, no embedding) — for analytics
    - Page-level records (structured extraction + Titan embedding) — for Q&A
    - Textract OCR for scanned pages
    - Textract table extraction for fee schedules
    - Resume capability on credential expiry
    """

    def __init__(
        self,
        session: AWSSession,
        index_manager: IndexManager,
        index_name: str,
        s3_bucket: str,
        s3_prefix: str,
        llm_model: str = DEFAULT_LLM_MODEL,
        embedding_model: str = DEFAULT_EMBEDDING_MODEL,
        state: str = "MS",
        session_id: str = None,
        batch_size: int = 50,
    ):
        self.session = session
        self.index_mgr = index_manager
        self.index_name = index_name
        self.s3_bucket = s3_bucket
        self.s3_prefix = s3_prefix
        self.llm_model = llm_model
        self.embedding_model = embedding_model
        self.state = state
        self.batch_size = batch_size

        self.s3 = session.client("s3")
        self.bedrock = session.client("bedrock-runtime")
        self.textract = session.client("textract")

        self.progress = IngestionProgress()
        self._load_progress()

        # Multi-session lease ledger (file-locked, on disk)
        self.lease = LeaseManager(index_name, session_id=session_id)
        # One-shot migration: fold any legacy progress into the ledger
        if self.progress.completed_keys or self.progress.failed_keys:
            self.lease.import_legacy_progress(
                list(self.progress.completed_keys),
                list(self.progress.failed_keys),
            )
        print("Session id: %s" % self.lease.session_id)

    # ── Progress tracking ───────────────────────────────────────────────

    def _load_progress(self):
        """Load progress from disk for resume capability."""
        progress_file = _progress_file(self.index_name)
        if os.path.exists(progress_file):
            with open(progress_file) as f:
                data = json.load(f)
                self.progress = IngestionProgress(**data)
            print("Resumed: %d docs already done" % len(self.progress.completed_keys))

    def _save_progress(self):
        """Save progress to disk."""
        self.progress.last_updated = datetime.utcnow()
        with open(_progress_file(self.index_name), "w") as f:
            json.dump(self.progress.model_dump(mode="json"), f, indent=2, default=str)

    # ── S3 listing ──────────────────────────────────────────────────────

    def list_pdfs(self):
        """
        List all PDFs in the S3 prefix.

        Auto-detects state and agency_type from S3 key structure:
          - Phase 1 (flat): source-documents/filename.pdf → state from self.state
          - Phase 2 (hierarchical): crawled-documents/TX/dental/file.pdf → state=TX, agency=dental
        """
        pdfs = []
        paginator = self.s3.get_paginator("list_objects_v2")

        for page in paginator.paginate(Bucket=self.s3_bucket, Prefix=self.s3_prefix):
            for obj in page.get("Contents", []):
                key = obj["Key"]
                if not key.lower().endswith(".pdf"):
                    continue
                if "proposal" in key.lower() or ".DS_Store" in key:
                    continue

                # Parse state/agency from key path
                relative = key.replace(self.s3_prefix, "").strip("/")
                parts = relative.split("/")

                if len(parts) >= 3:
                    # Hierarchical: STATE/agency_type/filename.pdf
                    state = parts[0].upper()
                    agency_type = parts[1].lower()
                    filename = parts[-1]
                else:
                    # Flat: filename.pdf
                    state = self.state
                    agency_type = ""
                    filename = parts[-1]

                pdfs.append({
                    "key": key,
                    "filename": filename,
                    "size": obj["Size"],
                    "state": state,
                    "agency_type": agency_type,
                })

        return pdfs

    # ── Main pipeline ───────────────────────────────────────────────────

    def run(self, dry_run=False, max_docs=None):
        """Run the full ingestion pipeline."""
        print("\n" + "=" * 60)
        print("V2 Ingestion Pipeline (Textract + Titan)")
        print("Index: %s" % self.index_name)
        print("Source: s3://%s/%s" % (self.s3_bucket, self.s3_prefix))
        print("=" * 60 + "\n")

        if not dry_run:
            self.index_mgr.create_index(self.index_name)

        print("Listing PDFs in S3...")
        all_pdfs = self.list_pdfs()
        print("Found %d PDFs" % len(all_pdfs))

        # Show ledger state across all sessions
        snap = self.lease.stats()
        print("Ledger: %d completed, %d failed, %d active sessions" % (
            snap["completed"], snap["failed"], len(snap["active_sessions"])))
        for s in snap["active_sessions"]:
            tag = " (this session)" if s["session"] == self.lease.session_id else ""
            print("  - %s: %d in flight%s" % (s["session"], s["in_flight"], tag))

        if dry_run:
            self._estimate_cost(all_pdfs)
            return

        self.progress.total_documents = len(all_pdfs)
        all_keys = [p["key"] for p in all_pdfs]
        pdf_by_key = {p["key"]: p for p in all_pdfs}

        start_time = time.time()
        processed_this_run = 0
        # Outer loop: keep claiming batches until none are left or max_docs hit
        while True:
            remaining_budget = (max_docs - processed_this_run) if max_docs else self.batch_size
            if remaining_budget <= 0:
                break
            claim_n = min(self.batch_size, remaining_budget)

            claimed = self.lease.claim_batch(all_keys, claim_n)
            if not claimed:
                print("\nNo more keys to claim — other sessions may still be working.")
                break

            print("\nClaimed %d docs for session %s" % (len(claimed), self.lease.session_id))

            for idx, key in enumerate(claimed, 1):
                pdf_info = pdf_by_key[key]

                # Refresh credentials periodically
                if (processed_this_run + idx) % CHECK_CREDS_EVERY_N_DOCS == 1:
                    self.session.ensure_valid()
                    self.s3 = self.session.client("s3")
                    self.bedrock = self.session.client("bedrock-runtime")
                    self.textract = self.session.client("textract")
                    self.index_mgr.refresh_client()

                print("\n[%d/%d in batch] %s (%dKB)" % (
                    idx, len(claimed), pdf_info["filename"], pdf_info["size"] // 1024))

                try:
                    self._process_document(pdf_info)
                    self.lease.mark_done(key)
                    self.progress.completed_keys.append(key)
                    processed_this_run += 1
                except SSOExpiredError:
                    print("\nSSO expired — releasing remaining claims and exiting...")
                    self.lease.release()
                    self._save_progress()
                    self._print_summary(time.time() - start_time)
                    print("\nRe-run after: aws sso login --profile <your-aws-profile>")
                    sys.exit(1)
                except KeyboardInterrupt:
                    print("\nInterrupted — releasing remaining claims...")
                    self.lease.release()
                    self._save_progress()
                    raise
                except Exception as exc:
                    print("  FAILED: %s" % exc)
                    traceback.print_exc()
                    self.lease.mark_failed(key)
                    self.progress.failed_keys.append(key)

                self._save_progress()

            # Done with this batch — heartbeat and loop to claim more
            self.lease.heartbeat()

        self._print_summary(time.time() - start_time)

    def _process_document(self, pdf_info):
        """Process a single PDF: download, extract, compress, index."""
        filename = pdf_info["filename"]
        s3_key = pdf_info["key"]
        doc_state = pdf_info.get("state", self.state)
        doc_agency = pdf_info.get("agency_type", "")
        # Use state+agency+filename for unique ID to avoid collisions across states
        doc_id = hashlib.sha256(("%s/%s/%s" % (doc_state, doc_agency, filename)).encode()).hexdigest()[:16]

        # Download from S3
        local_path = os.path.join(LOCAL_TMP_DIR, filename)
        Path(local_path).parent.mkdir(parents=True, exist_ok=True)
        self.s3.download_file(self.s3_bucket, s3_key, local_path)

        # Extract text from all pages via PyMuPDF
        pages = extract_pages(local_path)
        total_pages = len(pages)
        pages_with_text = sum(1 for p in pages if p["text"])
        print("  %d pages (%d with text, %d scanned)" % (total_pages, pages_with_text, total_pages - pages_with_text))

        # ── Phase 1: OCR scanned pages + table extraction ───────────
        ocr_count = 0
        table_count = 0
        for i, page in enumerate(pages):
            pnum = page["page_number"]
            image_bytes = None  # rendered on demand, reused if needed

            # OCR scanned pages
            if not page["text"]:
                try:
                    image_bytes = render_page_image(local_path, pnum)
                    page["text"] = textract_ocr(self.textract, image_bytes)
                    ocr_count += 1
                    self.progress.estimated_cost_usd += COST_TEXTRACT_OCR_PER_PAGE
                except Exception as exc:
                    print("  OCR failed p%d: %s" % (pnum, exc))

            # Table extraction
            if page["text"] and is_table_page(page["text"]):
                try:
                    if image_bytes is None:
                        image_bytes = render_page_image(local_path, pnum)
                    tables = textract_extract_tables(self.textract, image_bytes)
                    if tables:
                        table_text = format_tables_as_text(tables)
                        page["text"] = page["text"] + "\n\n" + table_text
                        page["_has_tables"] = True
                        table_count += 1
                    self.progress.estimated_cost_usd += COST_TEXTRACT_TABLE_PER_PAGE
                except Exception as exc:
                    print("  Table extract failed p%d: %s" % (pnum, exc))

            # Progress for pre-processing phase
            if (i + 1) % 20 == 0 or (i + 1) == total_pages:
                print("  Pre-processing: %d/%d pages (%.0f%%)" % (i + 1, total_pages, (i + 1) / total_pages * 100))

        if ocr_count:
            print("  OCR'd %d scanned pages" % ocr_count)
        if table_count:
            print("  Extracted tables from %d pages" % table_count)

        # ── Build document record (full text, no embedding) ─────────
        full_text = "\n\n".join(
            "[Page %d]\n%s" % (p["page_number"], p["text"])
            for p in pages if p["text"]
        )

        if not full_text.strip():
            print("  No text in entire document — skipping")
            return

        doc_record = {
            "record_type": "document",
            "doc_id": doc_id,
            "filename": filename,
            "s3_key": s3_key,
            "total_pages": total_pages,
            "full_text": full_text,
            "state": doc_state,
            "agency_type": doc_agency,
            "ingested_at": datetime.utcnow().isoformat(),
        }

        # ── Build page records (batched LLM extraction + embedding) ──
        page_records = []
        processable_pages = [p for p in pages if p["text"]]
        total_to_process = len(processable_pages)

        # Separate low-value pages (skip LLM) from pages needing extraction
        llm_pages = []
        skip_pages = []
        for p in processable_pages:
            if is_low_value_page(p["text"]):
                skip_pages.append(p)
            else:
                llm_pages.append(p)

        if skip_pages:
            print("  Skipping LLM for %d low-value pages (title/blank/TOC)" % len(skip_pages))

        # Process low-value pages (raw text only, no LLM, still embed)
        for page in skip_pages:
            page_num = page["page_number"]
            page_id = "%s_p%d" % (doc_id, page_num)
            page_record = self._build_page_record(
                page_id, doc_id, filename, s3_key, page_num, total_pages,
                page["text"], {}, page.get("_has_tables", False),
                state=doc_state, agency_type=doc_agency,
            )
            try:
                emb_text = create_embedding_text(page_record)
                page_record["text_embedding"] = get_text_embedding(
                    self.bedrock, self.embedding_model, emb_text,
                )
                self.progress.estimated_cost_usd += COST_EMBEDDING_PER_CALL
            except Exception as exc:
                print("  Page %d embed failed: %s" % (page_num, exc))
            page_records.append(page_record)

        # Batch LLM extraction — process BATCH_SIZE pages per Mistral call
        total_llm = len(llm_pages)
        pages_done = 0
        for batch_start in range(0, total_llm, BATCH_SIZE):
            batch = llm_pages[batch_start:batch_start + BATCH_SIZE]
            batch_data = [{"page_number": p["page_number"], "text": p["text"]} for p in batch]

            # Extract structured fields
            try:
                if len(batch) == 1:
                    # Single page — use single prompt (simpler, more reliable)
                    extracted_map = {
                        batch[0]["page_number"]: call_mistral_text(
                            self.bedrock, self.llm_model,
                            batch[0]["text"], filename, batch[0]["page_number"],
                        )
                    }
                    self.progress.estimated_cost_usd += COST_MISTRAL_TEXT_PER_CALL
                else:
                    # Batch — multiple pages in one call
                    extracted_map = call_mistral_batch(
                        self.bedrock, self.llm_model, batch_data, filename,
                    )
                    self.progress.estimated_cost_usd += COST_MISTRAL_BATCH_PER_CALL
                self.progress.total_text_extractions += len(batch)
            except Exception as exc:
                print("  Batch extraction failed (pages %s): %s" % (
                    ",".join(str(p["page_number"]) for p in batch), exc))
                extracted_map = {}

            # Build records for each page in the batch
            for page in batch:
                page_num = page["page_number"]
                page_id = "%s_p%d" % (doc_id, page_num)
                extracted = extracted_map.get(page_num, {
                    "abstract_text": page["text"][:500],
                })

                page_record = self._build_page_record(
                    page_id, doc_id, filename, s3_key, page_num, total_pages,
                    page["text"], extracted, page.get("_has_tables", False),
                    state=doc_state, agency_type=doc_agency,
                )

                # Embedding
                try:
                    emb_text = create_embedding_text(page_record)
                    page_record["text_embedding"] = get_text_embedding(
                        self.bedrock, self.embedding_model, emb_text,
                    )
                    self.progress.estimated_cost_usd += COST_EMBEDDING_PER_CALL
                except Exception as exc:
                    print("  Page %d embed failed: %s" % (page_num, exc))

                page_records.append(page_record)

            pages_done += len(batch)
            pct = pages_done / total_llm * 100 if total_llm else 100
            print("  LLM extract + embed: %d/%d pages (%.0f%%) | cost: $%.2f" % (
                pages_done, total_llm, pct, self.progress.estimated_cost_usd))

        self.progress.total_pages_processed += len(page_records)

        # Sort by page number for clean ordering
        page_records.sort(key=lambda r: r["page_number"])

        # ── Index everything ────────────────────────────────────────
        # Refresh credentials before indexing — large docs may have taken
        # long enough for the SSO token to expire during processing
        self.session.ensure_valid()
        self.index_mgr.refresh_client()

        all_records = [doc_record] + page_records
        try:
            indexed = self.index_mgr.bulk_index(self.index_name, all_records)
        except Exception as exc:
            if "403" in str(exc) or "expired" in str(exc).lower() or "security token" in str(exc).lower():
                # Token expired between check and index — refresh and retry once
                print("  Token expired during indexing, refreshing and retrying...")
                self.session.ensure_valid()
                self.index_mgr.refresh_client()
                indexed = self.index_mgr.bulk_index(self.index_name, all_records)
            else:
                raise
        print("  Indexed: 1 doc + %d pages (%d/%d ok)" % (len(page_records), indexed, len(all_records)))

        # Cleanup
        try:
            os.remove(local_path)
        except OSError:
            pass

    def _build_page_record(self, page_id, doc_id, filename, s3_key,
                           page_num, total_pages, text, extracted, has_tables,
                           state=None, agency_type=""):
        """Build a page record dict from extracted fields."""
        return {
            "record_type": "page",
            "page_id": page_id,
            "doc_id": doc_id,
            "filename": filename,
            "s3_key": s3_key,
            "page_number": page_num,
            "total_pages": total_pages,
            "raw_text": text,
            "abstract_text": extracted.get("abstract_text", text[:500]),
            "core_rule": extracted.get("core_rule"),
            "statute_codes": extracted.get("statute_codes", []),
            "compliance_requirements": extracted.get("compliance_requirements", []),
            "legal_entities": extracted.get("legal_entities", []),
            "section_identifier": extracted.get("section_identifier"),
            "document_type": extracted.get("document_type", "unknown"),
            "fee_amounts": _sanitize_fees(extracted.get("fee_amounts", [])),
            "effective_date": safe_date(extracted.get("effective_date")),
            "amendment_date": safe_date(extracted.get("amendment_date")),
            "license_categories": extracted.get("license_categories", []),
            "testing_requirements": extracted.get("testing_requirements"),
            "statutory_authority_references": extracted.get("statutory_authority_references", []),
            "reciprocity_provisions": extracted.get("reciprocity_provisions"),
            "is_table_page": has_tables,
            "used_vision": False,
            "extraction_model": self.llm_model if extracted else "",
            "state": state or self.state,
            "agency_type": agency_type,
            "ingested_at": datetime.utcnow().isoformat(),
        }

    # ── Cost estimation ─────────────────────────────────────────────────

    def _estimate_cost(self, pdfs):
        """Estimate processing cost without running."""
        total_size = sum(p["size"] for p in pdfs)
        avg_pages = 20
        total_pages = len(pdfs) * avg_pages
        table_pages = int(total_pages * 0.25)
        scanned_pages = int(total_pages * 0.05)
        skip_pages = int(total_pages * 0.10)  # ~10% low-value pages
        llm_pages = total_pages - skip_pages
        llm_calls = llm_pages / BATCH_SIZE  # batched

        mistral_cost = llm_calls * COST_MISTRAL_BATCH_PER_CALL
        textract_ocr_cost = scanned_pages * COST_TEXTRACT_OCR_PER_PAGE
        textract_table_cost = table_pages * COST_TEXTRACT_TABLE_PER_PAGE
        embed_cost = total_pages * COST_EMBEDDING_PER_CALL
        total_cost = mistral_cost + textract_ocr_cost + textract_table_cost + embed_cost

        print("\n" + "=" * 60)
        print("COST ESTIMATE (dry run) — batched, %d pages/call" % BATCH_SIZE)
        print("=" * 60)
        print("Documents: %d" % len(pdfs))
        print("Total size: %.1f MB" % (total_size / 1024 / 1024))
        print("Estimated pages: ~%d (~%d skip LLM, ~%d need LLM)" % (total_pages, skip_pages, llm_pages))
        print("  Mistral batched: ~%d calls x $%.3f = $%.2f" % (llm_calls, COST_MISTRAL_BATCH_PER_CALL, mistral_cost))
        print("  Textract OCR: ~%d pages x $%.4f = $%.2f" % (scanned_pages, COST_TEXTRACT_OCR_PER_PAGE, textract_ocr_cost))
        print("  Textract tables: ~%d pages x $%.3f = $%.2f" % (table_pages, COST_TEXTRACT_TABLE_PER_PAGE, textract_table_cost))
        print("  Titan embeddings: ~%d pages x $%.4f = $%.2f" % (total_pages, COST_EMBEDDING_PER_CALL, embed_cost))
        print("  " + "-" * 30)
        print("  ESTIMATED TOTAL: $%.2f" % total_cost)
        print("  (vs ~$%.2f without batching/skipping)" % (total_pages * COST_MISTRAL_TEXT_PER_CALL + textract_ocr_cost + textract_table_cost + embed_cost))
        print("=" * 60)

    def _print_summary(self, elapsed):
        """Print final summary."""
        print("\n" + "=" * 60)
        print("INGESTION COMPLETE")
        print("=" * 60)
        print("Time: %.1fs (%.1f min)" % (elapsed, elapsed / 60))
        print("Documents: %d/%d" % (len(self.progress.completed_keys), self.progress.total_documents))
        print("Failed: %d" % len(self.progress.failed_keys))
        print("Pages: %d" % self.progress.total_pages_processed)
        print("Mistral calls: %d" % self.progress.total_text_extractions)
        print("Estimated cost: $%.2f" % self.progress.estimated_cost_usd)

        if self.progress.failed_keys:
            print("\nFailed:")
            for key in self.progress.failed_keys:
                print("  - %s" % key)


# ── CLI ─────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="V2 Ingestion Pipeline")
    parser.add_argument("--index", default=PHASE1_INDEX, help="OpenSearch index name")
    parser.add_argument("--s3-bucket", default="ms-sos-legal-documents")
    parser.add_argument("--s3-prefix", default="source-documents")
    parser.add_argument("--profile", default="<your-aws-profile>", help="AWS SSO profile")
    parser.add_argument("--state", default="MS", help="State code for documents")
    parser.add_argument("--opensearch-endpoint", required=True, help="OpenSearch endpoint URL")
    parser.add_argument("--llm-model", default=DEFAULT_LLM_MODEL)
    parser.add_argument("--embedding-model", default=DEFAULT_EMBEDDING_MODEL)
    parser.add_argument("--dry-run", action="store_true", help="Estimate cost without processing")
    parser.add_argument("--max-docs", type=int, help="Process at most N documents this run")
    parser.add_argument("--resume", action="store_true", help="Resume from progress file")
    parser.add_argument("--reset", action="store_true", help="Delete progress and start fresh")
    parser.add_argument("--batch-size", type=int, default=50,
                        help="Docs to claim per batch (multi-session coordination)")
    parser.add_argument("--session-id", default=None,
                        help="Stable session id for multi-session runs (default: auto host-pid-uuid)")

    args = parser.parse_args()

    if args.reset:
        progress_file = _progress_file(args.index)
        if os.path.exists(progress_file):
            os.remove(progress_file)
            print("Progress file deleted: %s" % progress_file)

    # Initialize AWS session
    session = AWSSession(profile=args.profile)
    session.ensure_valid()

    # Initialize index manager
    index_mgr = IndexManager(session, args.opensearch_endpoint)

    # Run pipeline
    pipeline = IngestionPipeline(
        session=session,
        index_manager=index_mgr,
        index_name=args.index,
        s3_bucket=args.s3_bucket,
        s3_prefix=args.s3_prefix,
        llm_model=args.llm_model,
        embedding_model=args.embedding_model,
        state=args.state,
        session_id=args.session_id,
        batch_size=args.batch_size,
    )

    try:
        pipeline.run(dry_run=args.dry_run, max_docs=args.max_docs)
    finally:
        # Always release any unfinished claims so other sessions can pick them up
        try:
            pipeline.lease.release()
        except Exception:
            pass


if __name__ == "__main__":
    main()
