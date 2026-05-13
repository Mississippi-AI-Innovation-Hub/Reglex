"""
Term frequency agent — counts term appearances across documents with references.

Use case: "How many times does 'continuing education' appear in dental board rules?"
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class TermFrequencyResult:
    """Result from term frequency analysis."""
    answer: str = ""
    citations: list[dict[str, Any]] = field(default_factory=list)
    frequency_data: list[dict[str, Any]] = field(default_factory=list)
    total_count: int = 0


class TermFrequencyAgent:
    """
    Counts term appearances across regulatory documents with references.

    Searches for the term across documents, counts occurrences,
    and provides references for each match.
    """

    SYSTEM_PROMPT = """You are a legal research assistant specializing in regulatory term analysis.
Your task is to count and analyze how frequently a specific term or concept appears in regulatory documents.

REQUIREMENTS:
1. Report the total count of relevant matches found.
2. For each match, cite the document, section, and page.
3. Summarize the context in which the term is used.
4. Note any patterns in how the term is used across different regulations."""

    def __init__(self, opensearch_client, bedrock_client, model_id: str, embedding_model_id: str):
        self.os_client = opensearch_client
        self.bedrock = bedrock_client
        self.model_id = model_id
        self.embedding_model_id = embedding_model_id

    def execute(
        self,
        query: str,
        terms: list[str],
        *,
        filter_state: str | None = None,
        filter_agency_type: str | None = None,
        filter_states: list[str] | None = None,
        top_k: int = 20,
    ) -> TermFrequencyResult:
        """Count term frequency with references."""
        from backend.agents._search_helpers import hybrid_search, call_llm

        # Search broadly for the terms
        search_query = " ".join(terms) if terms else query
        results = hybrid_search(
            self.os_client, self.bedrock, self.embedding_model_id,
            search_query, top_k=top_k,
            filter_state=filter_state,
            filter_agency_type=filter_agency_type,
            filter_states=filter_states,
        )

        # Count occurrences in original text
        frequency_data = []
        total_count = 0
        for r in results:
            text = (r.get("original_text", "") + " " + r.get("abstract_text", "")).lower()
            for term in terms:
                count = text.count(term.lower())
                if count > 0:
                    total_count += count
                    frequency_data.append({
                        "term": term,
                        "count": count,
                        "document": r["source_document"],
                        "section": r.get("section_identifier", ""),
                        "pages": r.get("page_numbers", []),
                        "state": r.get("state", "MS"),
                        "context_snippet": r.get("abstract_text", "")[:200],
                    })

        # Generate summary
        freq_summary = "\n".join(
            f"- '{fd['term']}' found {fd['count']}x in {fd['document']} "
            f"(Section: {fd['section']}, Pages: {fd['pages']}, State: {fd['state']})"
            for fd in frequency_data
        )

        user_message = f"""Analyze the frequency of these terms: {', '.join(terms)}

FREQUENCY DATA:
Total occurrences: {total_count}
{freq_summary}

USER QUESTION: {query}

Provide a summary of how frequently these terms appear, with citations for each occurrence."""

        answer = call_llm(
            self.bedrock, self.model_id,
            system_prompt=self.SYSTEM_PROMPT,
            messages=[{"role": "user", "content": [{"text": user_message}]}],
        )

        citations = [
            {
                "document": fd["document"],
                "section": fd["section"],
                "pages": fd["pages"],
                "state": fd["state"],
                "relevance": 1.0,
            }
            for fd in frequency_data
        ]

        return TermFrequencyResult(
            answer=answer,
            citations=citations,
            frequency_data=frequency_data,
            total_count=total_count,
        )
