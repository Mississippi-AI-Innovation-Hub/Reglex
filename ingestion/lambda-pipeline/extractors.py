"""
Text extraction and OCR for the v2 ingestion pipeline.

Extraction modes:
  1. PyMuPDF text extraction — every page, always (free, fast)
  2. AWS Textract OCR — scanned pages with no extractable text
  3. AWS Textract table extraction — pages with tables/fee schedules
  4. LLM text compression (Mistral) — every page, structured fields from text

Flow per page:
  PyMuPDF → got text? ─No──→ Textract OCR → got text now? → continue
                       │
                       Yes → is_table_page? ─Yes─→ Textract tables → merge with text
                       │                     │
                       └── No ───────────────┘
                                             │
                                             ▼
                              Mistral text extraction (structured fields)
                                             │
                                             ▼
                              Titan text embedding
"""

from __future__ import annotations

import base64
import json
import re
import time
from typing import Any

import fitz  # PyMuPDF

from models import FeeRecord


# ── PDF Text Extraction (PyMuPDF) ───────────────────────────────────────

def extract_pages(pdf_path: str) -> list[dict]:
    """
    Extract text from each page of a PDF using PyMuPDF.

    Returns list of:
        {"page_number": int, "text": str}
    """
    pages = []
    doc = fitz.open(pdf_path)

    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text("text")
        pages.append({
            "page_number": page_num + 1,
            "text": text.strip() if text else "",
        })

    doc.close()
    return pages


def render_page_image(pdf_path: str, page_number: int, dpi: int = 200) -> bytes:
    """
    Render a specific page as a PNG image for Textract.

    Args:
        pdf_path: Path to the PDF file
        page_number: 1-based page number
        dpi: Resolution for rendering

    Returns:
        PNG image bytes
    """
    doc = fitz.open(pdf_path)
    page = doc[page_number - 1]
    zoom = dpi / 72.0
    mat = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat)
    image_bytes = pix.tobytes("png")
    doc.close()
    return image_bytes


# ── AWS Textract OCR + Table Extraction ─────────────────────────────────

def textract_ocr(textract_client, image_bytes: bytes) -> str:
    """
    Run Textract OCR on a page image to extract text from scanned pages.

    Uses synchronous detect_document_text API (no S3 needed).
    Returns extracted text as a single string.
    """
    response = textract_client.detect_document_text(
        Document={"Bytes": image_bytes}
    )

    lines = []
    for block in response.get("Blocks", []):
        if block["BlockType"] == "LINE":
            lines.append(block["Text"])

    return "\n".join(lines)


def textract_extract_tables(textract_client, image_bytes: bytes) -> list[list[list[str]]]:
    """
    Run Textract table extraction on a page image.

    Uses synchronous analyze_document API with TABLES feature.
    Returns list of tables, each table is a list of rows,
    each row is a list of cell values.

    Example return:
    [
        [
            ["License Type", "Fee", "Statutory Cap"],
            ["Dental", "$150.00", "$200.00"],
            ["Medical", "$300.00", "$500.00"],
        ]
    ]
    """
    response = textract_client.analyze_document(
        Document={"Bytes": image_bytes},
        FeatureTypes=["TABLES"],
    )

    # Build block lookup
    blocks = {b["Id"]: b for b in response.get("Blocks", [])}

    tables = []
    for block in response["Blocks"]:
        if block["BlockType"] != "TABLE":
            continue

        rows_dict = {}  # row_index -> {col_index: text}
        for rel in block.get("Relationships", []):
            if rel["Type"] != "CHILD":
                continue
            for cell_id in rel["Ids"]:
                cell = blocks.get(cell_id)
                if not cell or cell["BlockType"] != "CELL":
                    continue

                row_idx = cell["RowIndex"]
                col_idx = cell["ColumnIndex"]

                # Get cell text from child WORD blocks
                cell_text = ""
                for cell_rel in cell.get("Relationships", []):
                    if cell_rel["Type"] == "CHILD":
                        words = []
                        for word_id in cell_rel["Ids"]:
                            word_block = blocks.get(word_id)
                            if word_block and word_block["BlockType"] == "WORD":
                                words.append(word_block["Text"])
                        cell_text = " ".join(words)

                if row_idx not in rows_dict:
                    rows_dict[row_idx] = {}
                rows_dict[row_idx][col_idx] = cell_text

        # Convert to list of lists
        if rows_dict:
            max_row = max(rows_dict.keys())
            max_col = max(
                max(cols.keys()) for cols in rows_dict.values()
            )
            table = []
            for r in range(1, max_row + 1):
                row = []
                for c in range(1, max_col + 1):
                    row.append(rows_dict.get(r, {}).get(c, ""))
                table.append(row)
            tables.append(table)

    return tables


def format_tables_as_text(tables: list[list[list[str]]]) -> str:
    """
    Format extracted tables as clean, structured text for LLM consumption.

    Converts table data into a readable format that Mistral can
    reliably extract fees, requirements, etc. from.
    """
    if not tables:
        return ""

    parts = []
    for i, table in enumerate(tables):
        if not table:
            continue

        parts.append(f"\n[TABLE {i + 1}]")

        # Use first row as header if it looks like one
        header = table[0] if table else []
        for row_idx, row in enumerate(table):
            if row_idx == 0:
                parts.append(" | ".join(cell for cell in row))
                parts.append("-" * 40)
            else:
                # Format as "Header1: Value1, Header2: Value2" for clarity
                if header and len(header) == len(row):
                    pairs = []
                    for h, v in zip(header, row):
                        if v.strip():
                            pairs.append(f"{h}: {v}")
                    if pairs:
                        parts.append(", ".join(pairs))
                else:
                    parts.append(" | ".join(cell for cell in row))

    return "\n".join(parts)


# ── Table Detection Heuristic ───────────────────────────────────────────

def is_table_page(text: str) -> bool:
    """
    Heuristic to detect pages likely containing tables or fee schedules.

    Returns True if the page likely has tabular content that Textract
    should process for structured table extraction.
    """
    if not text or len(text) < 50:
        return False

    score = 0

    # Dollar amounts — strong signal for fee tables
    dollar_matches = re.findall(r'\$[\d,]+(?:\.\d{2})?', text)
    if len(dollar_matches) >= 3:
        score += 3
    elif len(dollar_matches) >= 1:
        score += 1

    # Fee/fine keywords
    fee_keywords = [
        "fee", "fine", "penalty", "charge", "cost", "rate",
        "schedule", "amount", "renewal", "application", "examination",
        "late fee", "reinstatement",
    ]
    keyword_count = sum(1 for kw in fee_keywords if kw in text.lower())
    if keyword_count >= 3:
        score += 2
    elif keyword_count >= 1:
        score += 1

    # Many short lines (typical of tables)
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    if lines:
        short_lines = sum(1 for l in lines if len(l) < 60)
        short_ratio = short_lines / len(lines)
        if short_ratio > 0.6 and len(lines) > 5:
            score += 2

    # Numbers aligned in columns (multiple numbers per line)
    lines_with_multiple_numbers = sum(
        1 for l in lines
        if len(re.findall(r'\d+', l)) >= 3
    )
    if lines_with_multiple_numbers >= 3:
        score += 2

    return score >= 3


# ── Low-value page detection ────────────────────────────────────────────

def is_low_value_page(text: str) -> bool:
    """
    Detect pages that don't need LLM extraction.

    Title pages, blank pages, table-of-contents, page breaks, headers-only.
    These get indexed with raw text (for term counting) but skip the
    expensive Mistral call.
    """
    if not text:
        return True
    stripped = text.strip()
    if len(stripped) < 80:
        return True
    # Mostly whitespace / page numbers
    alpha_chars = sum(1 for c in stripped if c.isalpha())
    if alpha_chars < 30:
        return True
    return False


# ── LLM Text Compression ───────────────────────────────────────────────

SINGLE_PAGE_PROMPT = """You are a legal document analyst. Extract structured information from this regulatory text.

<legal_text>
{text}
</legal_text>

<source_info>
Document: {filename}
Page: {page_number}
</source_info>

Return a JSON object with these fields. Use null for fields not present in the text:

{{
    "abstract_text": "2-4 sentence summary capturing legal intent and key provisions",
    "core_rule": "The primary rule or regulation in one sentence, or null",
    "statute_codes": ["Exact statute citations, e.g. 'Miss. Code Ann. § 75-1-101'"],
    "compliance_requirements": ["Specific obligations using action verbs"],
    "legal_entities": ["Agencies, boards, offices mentioned"],
    "section_identifier": "Section/Rule/Chapter number if stated, or null",
    "document_type": "statute|regulation|administrative_rule|procedural_rule|definition|fee_schedule|other",
    "fee_amounts": [
        {{"amount": 150.00, "fee_type": "renewal|application|fine|penalty|examination|late|other", "description": "what the fee is for", "statutory_cap": null}}
    ],
    "effective_date": "YYYY-MM-DD or null",
    "amendment_date": "YYYY-MM-DD or null",
    "license_categories": ["temporary", "permanent", "reciprocity", "provisional", "inactive", "retired"],
    "testing_requirements": "Exam/testing requirements verbatim, or null",
    "statutory_authority_references": ["Statutes granting rulemaking authority"],
    "reciprocity_provisions": "Out-of-state license recognition provisions, or null"
}}

Rules:
1. Preserve exact statute citation formatting
2. Extract ALL dollar amounts as fee_amounts
3. Use action verbs for compliance requirements
4. Only include license_categories actually mentioned
5. Return ONLY valid JSON, no other text"""


BATCH_PAGE_PROMPT = """You are a legal document analyst. Extract structured information from multiple pages of a regulatory document.

For EACH page below, produce a JSON object with the same fields. Return a JSON array with one object per page, in order.

{pages_block}

For each page, return:
{{
    "page_number": <the page number>,
    "abstract_text": "2-4 sentence summary capturing legal intent and key provisions",
    "core_rule": "The primary rule or regulation in one sentence, or null",
    "statute_codes": ["Exact statute citations"],
    "compliance_requirements": ["Specific obligations using action verbs"],
    "legal_entities": ["Agencies, boards, offices mentioned"],
    "section_identifier": "Section/Rule/Chapter number if stated, or null",
    "document_type": "statute|regulation|administrative_rule|procedural_rule|definition|fee_schedule|other",
    "fee_amounts": [
        {{"amount": 150.00, "fee_type": "renewal|application|fine|penalty|examination|late|other", "description": "what the fee is for", "statutory_cap": null}}
    ],
    "effective_date": "YYYY-MM-DD or null",
    "amendment_date": "YYYY-MM-DD or null",
    "license_categories": ["Only categories actually mentioned"],
    "testing_requirements": "Exam/testing requirements verbatim, or null",
    "statutory_authority_references": ["Statutes granting rulemaking authority"],
    "reciprocity_provisions": "Out-of-state license recognition provisions, or null"
}}

Rules:
1. Return a JSON ARRAY of objects, one per page, in order
2. Preserve exact statute citation formatting
3. Extract ALL dollar amounts as fee_amounts
4. Only include license_categories actually mentioned
5. Return ONLY valid JSON array, no other text"""


def call_mistral_text(
    bedrock_client,
    model_id,
    text,
    filename,
    page_number,
):
    """
    Call Mistral Large 3 to extract structured fields from a single page.
    """
    prompt = SINGLE_PAGE_PROMPT.format(
        text=text[:6000],
        filename=filename,
        page_number=page_number,
    )

    response = bedrock_client.converse(
        modelId=model_id,
        messages=[{"role": "user", "content": [{"text": prompt}]}],
        inferenceConfig={"maxTokens": 2048, "temperature": 0.1, "topP": 0.9},
    )

    response_text = response["output"]["message"]["content"][0]["text"]
    return _parse_json_response(response_text)


def call_mistral_batch(
    bedrock_client,
    model_id,
    pages_data,
    filename,
):
    """
    Call Mistral Large 3 to extract structured fields from MULTIPLE pages
    in a single LLM call. Cuts API calls by batch_size factor.

    Args:
        pages_data: list of {"page_number": int, "text": str}

    Returns:
        dict mapping page_number -> extracted fields
    """
    # Build the pages block
    parts = []
    total_chars = 0
    for pd in pages_data:
        # Cap each page to keep total under model context
        page_text = pd["text"][:3000]
        total_chars += len(page_text)
        parts.append(
            "<page number=\"%d\">\n%s\n</page>" % (pd["page_number"], page_text)
        )

    pages_block = "\n\n".join(parts)

    prompt = BATCH_PAGE_PROMPT.format(pages_block=pages_block)

    # Increase max_tokens for batch output
    max_tokens = min(4096, 1500 * len(pages_data))

    response = bedrock_client.converse(
        modelId=model_id,
        messages=[{"role": "user", "content": [{"text": prompt}]}],
        inferenceConfig={"maxTokens": max_tokens, "temperature": 0.1, "topP": 0.9},
    )

    response_text = response["output"]["message"]["content"][0]["text"]
    parsed = _parse_json_response(response_text)

    # parsed should be a list of dicts, one per page
    results = {}
    if isinstance(parsed, list):
        for item in parsed:
            pnum = item.get("page_number")
            if pnum is not None:
                results[pnum] = item
    elif isinstance(parsed, dict) and "page_number" in parsed:
        # Single result returned instead of array
        results[parsed["page_number"]] = parsed
    elif isinstance(parsed, dict):
        # Fallback: assume it's for the first page
        if pages_data:
            results[pages_data[0]["page_number"]] = parsed

    return results


# ── Embedding ───────────────────────────────────────────────────────────

def create_embedding_text(page_record: dict) -> str:
    """
    Build the text to embed for a page record.

    Combines structured abstract with raw text for a vector that
    captures both LLM-interpreted meaning and original legal language.
    """
    parts = []

    if page_record.get("abstract_text"):
        parts.append(page_record["abstract_text"])

    if page_record.get("core_rule"):
        parts.append("Core rule: %s" % page_record["core_rule"])

    if page_record.get("statute_codes"):
        parts.append("Statutes: %s" % ", ".join(page_record["statute_codes"]))

    if page_record.get("compliance_requirements"):
        parts.append("Requirements: %s" % "; ".join(page_record["compliance_requirements"]))

    if page_record.get("section_identifier"):
        parts.append("Section: %s" % page_record["section_identifier"])

    # Include raw text so the vector also represents actual legal language
    raw = page_record.get("raw_text", "")
    if raw:
        parts.append("Source text: %s" % raw[:2000])

    return " | ".join(parts)


def get_text_embedding(bedrock_client, model_id: str, text: str) -> list[float]:
    """Generate text embedding using Amazon Titan Embed Text v2."""
    body = json.dumps({"inputText": text[:8000], "dimensions": 1024, "normalize": True})

    response = bedrock_client.invoke_model(
        modelId=model_id,
        body=body,
        contentType="application/json",
        accept="application/json",
    )

    return json.loads(response["body"].read())["embedding"]


# ── Helpers ─────────────────────────────────────────────────────────────

def _parse_json_response(text: str) -> dict:
    """Parse JSON from LLM response, handling markdown code blocks."""
    cleaned = text.strip()
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
            "abstract_text": "[Parse error] %s" % text[:300],
            "core_rule": None,
            "statute_codes": [],
            "compliance_requirements": [],
            "legal_entities": [],
            "section_identifier": None,
            "document_type": "other",
            "fee_amounts": [],
            "license_categories": [],
            "statutory_authority_references": [],
            "_parse_error": str(e),
        }


def safe_date(value):
    """Convert a date value to ISO string, or None."""
    if not value or value == "null" or value == "None":
        return None
    try:
        from datetime import date as _date
        if isinstance(value, str):
            _date.fromisoformat(value)
            return value
    except (ValueError, TypeError):
        return None
    return None
