"""
Data models for the CLaRa Legal Analysis System.
Defines structures for documents, abstracts, and retrieval results.

Phase 2 adds CompressedAbstractV2 with multi-state metadata for
cross-jurisdiction comparison, fee analysis, and reciprocity tracking.
"""

from datetime import date, datetime
from typing import Any
from pydantic import BaseModel, Field


class DocumentChunk(BaseModel):
    """Represents a chunk of a source document before compression."""
    chunk_id: str = Field(description="Unique identifier for this chunk")
    document_name: str = Field(description="Source document filename")
    document_path: str = Field(description="Full path to source document")
    page_numbers: list[int] = Field(description="Page numbers this chunk spans")
    section_title: str | None = Field(default=None, description="Detected section title if any")
    raw_text: str = Field(description="Original raw text content")
    chunk_index: int = Field(description="Index of this chunk in the document")
    total_chunks: int = Field(description="Total chunks in the document")
    created_at: datetime = Field(default_factory=datetime.now)
    # Phase 2: multi-state provenance
    state: str = Field(default="MS", description="State code (MS, AL, TN, etc.)")
    agency_type: str = Field(default="", description="Agency type: medical, real_estate, dental")


class CompressedAbstract(BaseModel):
    """
    CLaRa-style compressed abstract of a legal document section.
    This is what gets embedded and stored in the vector database.
    """
    abstract_id: str = Field(description="Unique identifier for this abstract")

    # Source tracking (for citations)
    source_document: str = Field(description="Source document filename")
    source_path: str = Field(description="Full path to source document")
    page_numbers: list[int] = Field(description="Page numbers referenced")
    section_identifier: str | None = Field(
        default=None,
        description="Section/chapter identifier (e.g., 'Section 75-1-101')"
    )

    # Compressed content (the "latent" representation)
    abstract_text: str = Field(
        description="LLM-compressed summary capturing legal intent"
    )
    core_rule: str | None = Field(
        default=None,
        description="The primary rule or regulation stated"
    )
    statute_codes: list[str] = Field(
        default_factory=list,
        description="Specific statute codes mentioned (e.g., 'Miss. Code Ann. § 75-1-101')"
    )
    compliance_requirements: list[str] = Field(
        default_factory=list,
        description="Key compliance requirements extracted"
    )
    legal_entities: list[str] = Field(
        default_factory=list,
        description="Entities mentioned (agencies, offices, etc.)"
    )

    # Original text preserved for precise citation
    original_text: str = Field(
        description="Original raw text for precise quotes when needed"
    )

    # Metadata
    document_type: str = Field(
        default="unknown",
        description="Type: 'statute', 'regulation', 'administrative_rule', etc."
    )
    created_at: datetime = Field(default_factory=datetime.now)
    compression_model: str = Field(description="Model used for compression")

    def get_citation(self) -> str:
        """Generate a formal citation string."""
        pages = ", ".join(str(p) for p in self.page_numbers)
        section = f", {self.section_identifier}" if self.section_identifier else ""
        return f"{self.source_document}{section} (pp. {pages})"


# ── Phase 2: Multi-State Models ────────────────────────────────────────


class FeeRecord(BaseModel):
    """Extracted fee or fine from regulatory text."""
    amount: float = Field(description="Dollar amount of the fee/fine")
    fee_type: str = Field(description="Type: 'renewal', 'application', 'fine', 'penalty', 'examination', 'late'")
    description: str = Field(description="Description of what the fee is for")
    statutory_cap: float | None = Field(default=None, description="Statutory maximum if specified")


class CompressedAbstractV2(CompressedAbstract):
    """
    Extended compressed abstract with multi-state metadata for Phase 2.

    Adds: state/agency tracking, fee extraction, dates, license categories,
    testing requirements, statutory authority references, and reciprocity info.
    """
    # Multi-state identification
    state: str = Field(default="MS", description="State code: MS, AL, TN, LA, AR, GA, TX")
    agency_type: str = Field(default="", description="Agency type: medical, real_estate, dental")
    agency_name: str = Field(default="", description="Full agency name")

    # Fee and penalty extraction
    fee_amounts: list[FeeRecord] = Field(
        default_factory=list,
        description="Extracted fees, fines, and penalties"
    )

    # Temporal metadata
    effective_date: date | None = Field(default=None, description="Regulation adoption/effective date")
    amendment_date: date | None = Field(default=None, description="Last amendment date")

    # Licensing metadata
    license_categories: list[str] = Field(
        default_factory=list,
        description="License categories: 'temporary', 'permanent', 'reciprocity', 'provisional', etc."
    )
    testing_requirements: str | None = Field(
        default=None,
        description="Examination/testing requirements for licensure"
    )

    # Authority and reciprocity
    statutory_authority_references: list[str] = Field(
        default_factory=list,
        description="Statutory authority citations granting rulemaking power"
    )
    reciprocity_provisions: str | None = Field(
        default=None,
        description="Out-of-state licensure reciprocity provisions"
    )


class RetrievalResult(BaseModel):
    """Result from vector store retrieval."""
    abstract: CompressedAbstract = Field(description="Retrieved compressed abstract")
    similarity_score: float = Field(description="Cosine similarity score")
    rank: int = Field(description="Rank in retrieval results")


class ChatMessage(BaseModel):
    """A message in the chat conversation."""
    role: str = Field(description="'user' or 'assistant'")
    content: str = Field(description="Message content")
    timestamp: datetime = Field(default_factory=datetime.now)
    citations: list[str] = Field(
        default_factory=list,
        description="Citations referenced in this message"
    )


class ChatResponse(BaseModel):
    """Response from the chat system including citations."""
    answer: str = Field(description="The generated answer")
    citations: list[dict[str, Any]] = Field(
        default_factory=list,
        description="List of citations with source details"
    )
    retrieved_abstracts: list[RetrievalResult] = Field(
        default_factory=list,
        description="Abstracts used to generate the answer"
    )
    confidence_note: str | None = Field(
        default=None,
        description="Any caveats about the response"
    )
    # Phase 2: enhanced response metadata
    intent: str = Field(default="general_research", description="Detected query intent")
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Structured metadata: comparison tables, frequency data, fee analysis, etc."
    )


class IngestionStats(BaseModel):
    """Statistics from document ingestion process."""
    total_documents: int = Field(default=0)
    total_pages: int = Field(default=0)
    total_chunks: int = Field(default=0)
    total_abstracts: int = Field(default=0)
    failed_documents: list[str] = Field(default_factory=list)
    processing_time_seconds: float = Field(default=0.0)
    documents_processed: list[str] = Field(default_factory=list)
