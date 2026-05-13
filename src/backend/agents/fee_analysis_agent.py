"""
Fee analysis agent — fee/fine comparison and benchmarking across states.

Use cases:
- "What fees does the MS dental board charge vs statutory caps?"
- "Compare medical board renewal fees across all 7 states"
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class FeeAnalysisResult:
    """Result from fee analysis."""
    answer: str = ""
    citations: list[dict[str, Any]] = field(default_factory=list)
    fee_table: list[dict[str, Any]] = field(default_factory=list)
    states_analyzed: list[str] = field(default_factory=list)


class FeeAnalysisAgent:
    """
    Analyzes fees, fines, and penalties across regulatory documents.

    Supports both single-state analysis (fees vs statutory caps)
    and cross-state benchmarking.
    """

    SYSTEM_PROMPT = """You are a legal research assistant specializing in regulatory fee analysis.
Your task is to analyze and compare fees, fines, and penalties from regulatory documents.

REQUIREMENTS:
1. List each fee with its dollar amount, type, and source citation.
2. If statutory caps are mentioned, compare actual fees to the caps.
3. For cross-state comparisons, present fees in a structured table.
4. Note any fees that appear to exceed statutory authority.
5. Include the effective date of fee schedules when available."""

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
    ) -> FeeAnalysisResult:
        """Analyze fees across documents/states."""
        from backend.agents._search_helpers import hybrid_search, call_llm

        fee_query = f"fee fine penalty amount dollar {query}"

        if states and len(states) > 1:
            # Cross-state benchmarking
            all_results = []
            for state in states:
                results = hybrid_search(
                    self.os_client, self.bedrock, self.embedding_model_id,
                    fee_query, top_k=top_k // len(states) + 1,
                    filter_state=state,
                    filter_agency_type=agency_type,
                )
                all_results.extend(results)
        else:
            all_results = hybrid_search(
                self.os_client, self.bedrock, self.embedding_model_id,
                fee_query, top_k=top_k,
                filter_state=states[0] if states else None,
                filter_agency_type=agency_type,
            )

        # Extract fee data from results
        fee_table = []
        for r in all_results:
            for fee in r.get("fee_amounts", []):
                fee_table.append({
                    "state": r.get("state", "MS"),
                    "agency_type": r.get("agency_type", ""),
                    "fee_type": fee.get("fee_type", "unknown"),
                    "amount": fee.get("amount", 0),
                    "description": fee.get("description", ""),
                    "statutory_cap": fee.get("statutory_cap"),
                    "document": r["source_document"],
                    "section": r.get("section_identifier", ""),
                    "pages": r.get("page_numbers", []),
                })

        # Build fee context
        fee_context = "\n".join(
            f"- {ft['state']}: ${ft['amount']:.2f} ({ft['fee_type']}) — {ft['description']} "
            f"[{ft['document']}, Section: {ft['section']}]"
            + (f" (Statutory cap: ${ft['statutory_cap']:.2f})" if ft["statutory_cap"] else "")
            for ft in fee_table
        )

        user_message = f"""Analyze the following fee data:

FEE DATA:
{fee_context if fee_context else "No structured fee data found in the retrieved documents."}

RETRIEVED DOCUMENTS:
{chr(10).join(f"- {r['source_document']} ({r.get('state', 'MS')}): {r['abstract_text'][:200]}" for r in all_results)}

USER QUESTION: {query}

Provide a fee analysis with a comparison table if multiple states are involved."""

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
            for r in all_results
        ]

        return FeeAnalysisResult(
            answer=answer,
            citations=citations,
            fee_table=fee_table,
            states_analyzed=states or [],
        )
