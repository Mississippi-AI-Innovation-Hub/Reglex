"""
Licensing reciprocity agent — analyzes out-of-state licensure reciprocity provisions.

Use case: "Does Mississippi recognize dental licenses from Tennessee?"
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ReciprocityResult:
    """Result from reciprocity analysis."""
    answer: str = ""
    citations: list[dict[str, Any]] = field(default_factory=list)
    reciprocity_data: list[dict[str, Any]] = field(default_factory=list)


class ReciprocityAgent:
    """Analyzes licensing reciprocity provisions across states."""

    SYSTEM_PROMPT = """You are a legal research assistant specializing in professional licensing reciprocity.
Your task is to analyze how states handle out-of-state license recognition.

REQUIREMENTS:
1. Identify whether a state has reciprocity provisions for the given license type.
2. List specific requirements for out-of-state applicants (exams, fees, experience).
3. Note any restrictions or limitations on reciprocal licenses.
4. Compare reciprocity provisions across states when multiple are analyzed.
5. Cite the specific regulation or statute for each provision."""

    def __init__(self, opensearch_client, bedrock_client, model_id: str, embedding_model_id: str):
        self.os_client = opensearch_client
        self.bedrock = bedrock_client
        self.model_id = model_id
        self.embedding_model_id = embedding_model_id

    def execute(
        self,
        query: str,
        *,
        states: list[str] | None = None,
        agency_type: str | None = None,
        top_k: int = 10,
    ) -> ReciprocityResult:
        """Analyze reciprocity provisions."""
        from backend.agents._search_helpers import hybrid_search, format_context, call_llm

        recip_query = f"reciprocity out-of-state license endorsement {query}"

        results = hybrid_search(
            self.os_client, self.bedrock, self.embedding_model_id,
            recip_query, top_k=top_k,
            filter_agency_type=agency_type,
            filter_states=states,
        )

        context = format_context(results)

        # Extract reciprocity-specific data
        reciprocity_data = []
        for r in results:
            if r.get("reciprocity_provisions") or r.get("license_categories"):
                reciprocity_data.append({
                    "state": r.get("state", "MS"),
                    "provisions": r.get("reciprocity_provisions", ""),
                    "license_categories": r.get("license_categories", []),
                    "document": r["source_document"],
                    "section": r.get("section_identifier", ""),
                })

        user_message = f"""Analyze licensing reciprocity provisions from the following documents:

{context}

USER QUESTION: {query}

Provide a detailed reciprocity analysis, comparing provisions across states if applicable."""

        answer = call_llm(
            self.bedrock, self.model_id,
            system_prompt=self.SYSTEM_PROMPT,
            messages=[{"role": "user", "content": [{"text": user_message}]}],
        )

        citations = [
            {
                "document": r["source_document"],
                "section": r.get("section_identifier"),
                "pages": r.get("page_numbers", []),
                "state": r.get("state", "MS"),
                "relevance": round(r["score"], 3),
            }
            for r in results
        ]

        return ReciprocityResult(
            answer=answer,
            citations=citations,
            reciprocity_data=reciprocity_data,
        )
