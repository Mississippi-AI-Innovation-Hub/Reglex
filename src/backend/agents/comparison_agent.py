"""
Cross-jurisdiction comparison agent.

Compares regulations across multiple states for a given topic/agency type.
Produces structured comparison tables.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ComparisonResult:
    """Result from cross-jurisdiction comparison."""
    answer: str = ""
    citations: list[dict[str, Any]] = field(default_factory=list)
    comparison_table: list[dict[str, Any]] = field(default_factory=list)
    states_compared: list[str] = field(default_factory=list)


class ComparisonAgent:
    """
    Compares regulations across multiple states for the same agency type.

    Searches each state independently, then synthesizes results into
    a side-by-side comparison with a structured table.
    """

    SYSTEM_PROMPT = """You are a legal research assistant specializing in cross-jurisdiction regulatory comparison.
Your role is to compare how different states regulate the same topic.

CRITICAL REQUIREMENTS:
1. Compare provisions state-by-state with specific citations.
2. Present differences clearly — what one state requires that another does not.
3. Include a structured comparison for each state with: state, provision summary, and citation.
4. If a state lacks relevant provisions, explicitly note that gap.
5. Format your response with a clear comparison section."""

    def __init__(self, opensearch_client, bedrock_client, model_id: str, embedding_model_id: str):
        self.os_client = opensearch_client
        self.bedrock = bedrock_client
        self.model_id = model_id
        self.embedding_model_id = embedding_model_id

    def execute(
        self,
        query: str,
        *,
        states: list[str],
        agency_type: str | None = None,
        top_k_per_state: int = 3,
    ) -> ComparisonResult:
        """Compare regulations across states."""
        from backend.agents._search_helpers import hybrid_search, format_context, call_llm

        all_results: dict[str, list[dict]] = {}
        all_citations = []

        for state in states:
            results = hybrid_search(
                self.os_client, self.bedrock, self.embedding_model_id,
                query, top_k=top_k_per_state,
                filter_state=state,
                filter_agency_type=agency_type,
            )
            all_results[state] = results

            for r in results:
                all_citations.append({
                    "document": r["source_document"],
                    "section": r.get("section_identifier"),
                    "pages": r["page_numbers"],
                    "statute_codes": r.get("statute_codes", []),
                    "relevance": round(r["score"], 3),
                    "state": r.get("state", state),
                    "agency_type": r.get("agency_type", ""),
                })

        # Build per-state context
        context_parts = []
        for state, results in all_results.items():
            context_parts.append(f"\n=== {state} ===")
            context_parts.append(format_context(results))

        combined_context = "\n".join(context_parts)

        user_message = f"""Compare the following regulations across states: {', '.join(states)}

RETRIEVED LEGAL CONTEXT BY STATE:
{combined_context}

USER QUESTION: {query}

Provide a structured comparison. For each state, summarize the relevant provisions with citations.
End with a comparison table in this format:

| State | Key Provision | Citation | Notable Differences |
|-------|--------------|----------|-------------------|"""

        answer = call_llm(
            self.bedrock, self.model_id,
            system_prompt=self.SYSTEM_PROMPT,
            messages=[{"role": "user", "content": [{"text": user_message}]}],
        )

        # Build comparison table metadata
        comparison_table = []
        for state, results in all_results.items():
            for r in results:
                comparison_table.append({
                    "state": state,
                    "provision": r.get("core_rule", r.get("abstract_text", "")[:200]),
                    "citation": r["source_document"],
                    "section": r.get("section_identifier", ""),
                    "statute_codes": r.get("statute_codes", []),
                })

        return ComparisonResult(
            answer=answer,
            citations=all_citations,
            comparison_table=comparison_table,
            states_compared=states,
        )
