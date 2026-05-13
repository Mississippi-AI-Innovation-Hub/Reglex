"""
Data models for the v2 ingestion pipeline.

Two record types per index:
  - DocumentRecord: one per PDF, full text, no embedding. For analytics/counting.
  - PageRecord: one per page, structured extraction + embedding. For Q&A retrieval.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, List, Optional

from pydantic import BaseModel, Field


class FeeRecord(BaseModel):
    """A single fee/fine extracted from a page."""
    amount: float
    fee_type: str = Field(description="renewal|application|fine|penalty|examination|late|other")
    description: str = ""
    statutory_cap: Optional[float] = None


class DocumentRecord(BaseModel):
    """
    One record per PDF file. Stores the full concatenated text for
    analytics queries (term counting, exhaustive search).

    No embedding vector — too much text for a single embedding.
    Queried via BM25 full-text search and scroll/aggregation APIs.
    """
    record_type: str = "document"
    doc_id: str = Field(description="Unique ID: hash of filename")
    filename: str
    s3_key: str
    total_pages: int
    full_text: str = Field(description="Complete concatenated text from all pages")
    # Metadata extracted from first/last pages
    title: Optional[str] = None
    board_or_agency: Optional[str] = None
    # Phase 2 fields
    state: str = "MS"
    agency_type: str = ""
    agency_name: str = ""
    ingested_at: datetime = Field(default_factory=datetime.utcnow)


class PageRecord(BaseModel):
    """
    One record per PDF page. The primary unit for retrieval.

    Contains both raw text (for BM25) and structured extraction
    (from LLM compression or Mistral vision for table pages).
    Embedding is generated from the structured abstract + raw text.
    """
    record_type: str = "page"
    page_id: str = Field(description="Unique ID: doc_id + page_number")
    doc_id: str = Field(description="Parent document ID")
    filename: str
    s3_key: str
    page_number: int
    total_pages: int

    # Raw extracted text (PyMuPDF)
    raw_text: str

    # LLM-extracted structured fields
    abstract_text: str = ""
    core_rule: Optional[str] = None
    statute_codes: List[str] = Field(default_factory=list)
    compliance_requirements: List[str] = Field(default_factory=list)
    legal_entities: List[str] = Field(default_factory=list)
    section_identifier: Optional[str] = None
    document_type: str = "unknown"

    # Structured data (fees, dates, licensing)
    fee_amounts: List[FeeRecord] = Field(default_factory=list)
    effective_date: Optional[date] = None
    amendment_date: Optional[date] = None
    license_categories: List[str] = Field(default_factory=list)
    testing_requirements: Optional[str] = None
    statutory_authority_references: List[str] = Field(default_factory=list)
    reciprocity_provisions: Optional[str] = None

    # Processing metadata
    is_table_page: bool = False
    used_vision: bool = False
    extraction_model: str = ""

    # Phase 2 fields
    state: str = "MS"
    agency_type: str = ""
    agency_name: str = ""
    ingested_at: datetime = Field(default_factory=datetime.utcnow)


class IngestionProgress(BaseModel):
    """Tracks ingestion progress for resume capability."""
    completed_keys: List[str] = Field(default_factory=list)
    failed_keys: List[str] = Field(default_factory=list)
    total_documents: int = 0
    total_pages_processed: int = 0
    total_vision_calls: int = 0
    total_text_extractions: int = 0
    estimated_cost_usd: float = 0.0
    last_updated: datetime = Field(default_factory=datetime.utcnow)
