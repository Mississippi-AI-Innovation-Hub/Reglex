"""
Bedrock-powered Compression Agent for CLaRa Legal Analysis System.
"""

import json
import hashlib
from typing import Optional, Callable
import boto3

from config import config
from models import DocumentChunk, CompressedAbstract, CompressedAbstractV2, FeeRecord


# import time
# import threading

# class SmoothRateLimiter:
#     """
#     Thread-safe, smooth rate limiter.
#     Ensures at most `rpm` requests per minute by spacing calls ~evenly.
#     """
#     def __init__(self, rpm: float):
#         if rpm <= 0:
#             raise ValueError("rpm must be > 0")
#         self.interval = 60.0 / rpm
#         self.lock = threading.Lock()
#         self.next_allowed = 0.0  # monotonic time

#     def acquire(self):
#         with self.lock:
#             now = time.monotonic()
#             if now < self.next_allowed:
#                 time.sleep(self.next_allowed - now)
#                 now = time.monotonic()
#             self.next_allowed = max(self.next_allowed + self.interval, now + self.interval)

# BEDROCK_RPM_PER_PROCESS = 5

# _rate_limiter = SmoothRateLimiter(BEDROCK_RPM_PER_PROCESS)

# V1 prompt (backward compatible)
COMPRESSION_PROMPT = """You are a legal document analyst specializing in Mississippi state law.
Your task is to compress the following legal text into a structured, information-rich abstract.

IMPORTANT: Extract and preserve ALL statutory references, section numbers, and legal citations exactly as they appear.

<legal_text>
{text}
</legal_text>

<source_metadata>
Document: {document_name}
Pages: {pages}
</source_metadata>

Analyze this legal text and provide a JSON response with the following structure:

{{
    "abstract_text": "A dense 2-4 sentence summary capturing the legal intent, scope, and key provisions. Include relevant statute numbers.",
    "core_rule": "The primary rule, requirement, or regulation stated in one clear sentence.",
    "statute_codes": ["List of specific statute codes mentioned, e.g., 'Miss. Code Ann. § 75-1-101'"],
    "compliance_requirements": ["List of specific compliance requirements, duties, or obligations mentioned"],
    "legal_entities": ["List of agencies, offices, positions, or entities mentioned"],
    "section_identifier": "The section/chapter identifier if clearly stated (e.g., 'Section 75-1-101', 'Rule 1.1'), or null if not present",
    "document_type": "One of: 'statute', 'regulation', 'administrative_rule', 'procedural_rule', 'definition', 'other'"
}}

Guidelines:
1. Be precise with statute citations - preserve exact formatting (e.g., "§", "Ann.", section numbers)
2. For compliance requirements, use action verbs (e.g., "Must file annual report by March 1")
3. The abstract should be searchable - include key legal terms someone might query
4. If the text is a definition section, clearly note what terms are being defined
5. Preserve any cross-references to other statutes or regulations

Return ONLY the JSON object, no additional text."""

# V2 prompt — extended extraction for multi-state regulatory analysis
COMPRESSION_PROMPT_V2 = """You are a legal document analyst specializing in state regulatory law across the United States.
Your task is to compress the following legal text into a structured, information-rich abstract.

IMPORTANT: Extract and preserve ALL statutory references, section numbers, legal citations, fees, dates, and licensing provisions exactly as they appear.

<legal_text>
{text}
</legal_text>

<source_metadata>
Document: {document_name}
Pages: {pages}
State: {state}
Agency Type: {agency_type}
Agency Name: {agency_name}
</source_metadata>

Analyze this legal text and provide a JSON response with the following structure:

{{
    "abstract_text": "A dense 2-4 sentence summary capturing the legal intent, scope, and key provisions. Include relevant statute numbers.",
    "core_rule": "The primary rule, requirement, or regulation stated in one clear sentence.",
    "statute_codes": ["List of specific statute codes mentioned, e.g., 'Miss. Code Ann. § 75-1-101'"],
    "compliance_requirements": ["List of specific compliance requirements, duties, or obligations mentioned"],
    "legal_entities": ["List of agencies, offices, positions, or entities mentioned"],
    "section_identifier": "The section/chapter identifier if clearly stated, or null",
    "document_type": "One of: 'statute', 'regulation', 'administrative_rule', 'procedural_rule', 'definition', 'other'",
    "fee_amounts": [
        {{
            "amount": 150.00,
            "fee_type": "renewal|application|fine|penalty|examination|late",
            "description": "Brief description of the fee",
            "statutory_cap": null
        }}
    ],
    "effective_date": "YYYY-MM-DD or null if not mentioned",
    "amendment_date": "YYYY-MM-DD or null if not mentioned",
    "license_categories": ["temporary", "permanent", "reciprocity", "provisional", "inactive", "retired"],
    "testing_requirements": "Description of any exam or testing requirements for licensure, or null",
    "statutory_authority_references": ["Citations to statutes that grant rulemaking authority to the agency"],
    "reciprocity_provisions": "Description of out-of-state licensure reciprocity provisions, or null"
}}

Guidelines:
1. Be precise with statute citations — preserve exact formatting (§, Ann., section numbers)
2. For compliance requirements, use action verbs (e.g., "Must file annual report by March 1")
3. Extract ALL dollar amounts as fee_amounts with appropriate fee_type classification
4. If a statutory cap on fees is mentioned, include it in statutory_cap
5. Extract effective/amendment dates in ISO format (YYYY-MM-DD) when clearly stated
6. Identify ALL license categories mentioned (temporary, permanent, reciprocity, etc.)
7. Capture any examination or testing requirements verbatim
8. Identify statutory authority references — the statutes that authorize the agency to make rules
9. Capture reciprocity provisions — how out-of-state licenses are recognized
10. The abstract should be searchable — include key legal terms someone might query

Return ONLY the JSON object, no additional text."""


class BedrockCompressionAgent:
    """
    Bedrock-powered agent for compressing raw legal text into structured abstracts.
    """
    
    def __init__(self):
        if not config.aws:
            raise ValueError("AWS configuration not set. Set USE_AWS=true in .env")
        
        self.config = config.aws
        self._init_bedrock_client()
    
    def _init_bedrock_client(self):
        """Initialize Bedrock runtime client."""
        self.client = boto3.client(
            service_name='bedrock-runtime',
            region_name=self.config.region
        )
    
    def _generate_abstract_id(self, chunk: DocumentChunk) -> str:
        """Generate a unique ID for the abstract based on content hash."""
        content = f"{chunk.document_name}:{chunk.page_numbers}:{chunk.raw_text[:500]}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]
    
    def _call_bedrock(self, prompt: str) -> str:
        """
        Call Bedrock model using the Converse API (model-agnostic).
        
        The Converse API provides a unified format across ALL Bedrock models
        (Mistral, Claude, Llama, Cohere, etc.) — no model-specific request
        schemas to maintain. Supports inference profile ARNs natively.
        """
        model_id = self.config.bedrock_llm_model
        
        response = self.client.converse(
            modelId=model_id,
            messages=[
                {
                    "role": "user",
                    "content": [{"text": prompt}]
                }
            ],
            inferenceConfig={
                "maxTokens": 4096,
                "temperature": 0.1,
                "topP": 0.9
            }
        )
        
        return response['output']['message']['content'][0]['text']

    
    def _parse_llm_response(self, response: str) -> dict:
        """Parse JSON response from LLM."""
        cleaned = response.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        if cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()
        
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            return {
                "abstract_text": f"[Parsing error] {response[:500]}",
                "core_rule": None,  # Allow None for parsing errors
                "statute_codes": [],
                "compliance_requirements": [],
                "legal_entities": [],
                "section_identifier": None,
                "document_type": "other",
                "_parse_error": str(e)
            }
    
    def compress(self, chunk: DocumentChunk) -> CompressedAbstract:
        """Compress a document chunk into a structured abstract (V1)."""
        pages_str = ", ".join(str(p) for p in chunk.page_numbers)
        prompt = COMPRESSION_PROMPT.format(
            text=chunk.raw_text,
            document_name=chunk.document_name,
            pages=pages_str
        )

        response = self._call_bedrock(prompt)
        parsed = self._parse_llm_response(response)

        # Helper to safely convert to string or None
        def safe_str_or_none(value):
            if value is None or value == "null":
                return None
            if isinstance(value, str):
                return value.strip() if value.strip() else None
            return str(value) if value else None

        return CompressedAbstract(
            abstract_id=self._generate_abstract_id(chunk),
            source_document=chunk.document_name,
            source_path=chunk.document_path,
            page_numbers=chunk.page_numbers,
            section_identifier=safe_str_or_none(parsed.get("section_identifier")),
            abstract_text=parsed.get("abstract_text") or "[No abstract generated]",
            core_rule=safe_str_or_none(parsed.get("core_rule")),
            statute_codes=parsed.get("statute_codes", []),
            compliance_requirements=parsed.get("compliance_requirements", []),
            legal_entities=parsed.get("legal_entities", []),
            original_text=chunk.raw_text,
            document_type=parsed.get("document_type", "unknown"),
            compression_model=self.config.bedrock_llm_model
        )

    def compress_v2(
        self,
        chunk: DocumentChunk,
        state: str = "MS",
        agency_type: str = "",
        agency_name: str = "",
    ) -> CompressedAbstractV2:
        """Compress a document chunk into a V2 abstract with multi-state metadata."""
        pages_str = ", ".join(str(p) for p in chunk.page_numbers)
        prompt = COMPRESSION_PROMPT_V2.format(
            text=chunk.raw_text,
            document_name=chunk.document_name,
            pages=pages_str,
            state=state,
            agency_type=agency_type,
            agency_name=agency_name,
        )

        response = self._call_bedrock(prompt)
        parsed = self._parse_llm_response(response)

        def safe_str_or_none(value):
            if value is None or value == "null":
                return None
            if isinstance(value, str):
                return value.strip() if value.strip() else None
            return str(value) if value else None

        def safe_date(value):
            if not value or value == "null":
                return None
            try:
                from datetime import date as _date
                return _date.fromisoformat(str(value))
            except (ValueError, TypeError):
                return None

        # Parse fee_amounts
        fee_records = []
        for fee_data in parsed.get("fee_amounts", []):
            if isinstance(fee_data, dict):
                try:
                    fee_records.append(FeeRecord(
                        amount=float(fee_data.get("amount", 0)),
                        fee_type=str(fee_data.get("fee_type", "other")),
                        description=str(fee_data.get("description", "")),
                        statutory_cap=float(fee_data["statutory_cap"]) if fee_data.get("statutory_cap") else None,
                    ))
                except (ValueError, TypeError):
                    pass

        return CompressedAbstractV2(
            abstract_id=self._generate_abstract_id(chunk),
            source_document=chunk.document_name,
            source_path=chunk.document_path,
            page_numbers=chunk.page_numbers,
            section_identifier=safe_str_or_none(parsed.get("section_identifier")),
            abstract_text=parsed.get("abstract_text") or "[No abstract generated]",
            core_rule=safe_str_or_none(parsed.get("core_rule")),
            statute_codes=parsed.get("statute_codes", []),
            compliance_requirements=parsed.get("compliance_requirements", []),
            legal_entities=parsed.get("legal_entities", []),
            original_text=chunk.raw_text,
            document_type=parsed.get("document_type", "unknown"),
            compression_model=self.config.bedrock_llm_model,
            # V2 fields
            state=state or chunk.state if hasattr(chunk, "state") else "MS",
            agency_type=agency_type or getattr(chunk, "agency_type", ""),
            agency_name=agency_name,
            fee_amounts=fee_records,
            effective_date=safe_date(parsed.get("effective_date")),
            amendment_date=safe_date(parsed.get("amendment_date")),
            license_categories=parsed.get("license_categories", []),
            testing_requirements=safe_str_or_none(parsed.get("testing_requirements")),
            statutory_authority_references=parsed.get("statutory_authority_references", []),
            reciprocity_provisions=safe_str_or_none(parsed.get("reciprocity_provisions")),
        )
    
    def compress_batch(
        self,
        chunks: list[DocumentChunk],
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> list[CompressedAbstract]:
        """Compress multiple chunks."""
        abstracts = []
        total = len(chunks)
        
        # Helper to safely convert to string or None
        def safe_str_or_none(value):
            if value is None or value == "null":
                return None
            if isinstance(value, str):
                return value.strip() if value.strip() else None
            # Handle unexpected types (list, dict, bool, etc.)
            return str(value) if value else None
        
        for i, chunk in enumerate(chunks):
            try:
                abstract = self.compress(chunk)
                abstracts.append(abstract)
            except Exception as e:
                #print(f"Error compressing chunk {chunk.chunk_id}: {e}")
                # Create fallback abstract
                abstracts.append(CompressedAbstract(
                    abstract_id=self._generate_abstract_id(chunk),
                    source_document=chunk.document_name,
                    source_path=chunk.document_path,
                    page_numbers=chunk.page_numbers,
                    section_identifier=safe_str_or_none(chunk.section_title),
                    abstract_text=f"[Compression failed] {chunk.raw_text[:200]}...",
                    core_rule=None,
                    statute_codes=[],
                    compliance_requirements=[],
                    legal_entities=[],
                    original_text=chunk.raw_text,
                    document_type="unknown",
                    compression_model=self.config.bedrock_llm_model
                ))
            
            if progress_callback:
                progress_callback(i + 1, total)
        
        return abstracts

