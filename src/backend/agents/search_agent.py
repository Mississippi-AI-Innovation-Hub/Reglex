"""
Enhanced search agent — general-purpose regulatory search.

Upgrades the current lambda_handler's search-then-LLM flow with:
- Hybrid search (kNN + BM25 + RRF) via OpenSearchVectorStore
- State/agency filtering
- Multi-turn conversation context
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class SearchResult:
    """Result from the search agent."""
    answer: str = ""
    citations: list[dict[str, Any]] = field(default_factory=list)
    search_results_count: int = 0


class SearchAgent:
    """
    General search agent for regulatory document retrieval.

    Uses hybrid search (kNN + BM25 + RRF) and generates an LLM response
    with citations from the retrieved context.
    """

    SYSTEM_PROMPT = """You are a legal research assistant for the Mississippi Secretary of State's office.
Your role is to help staff verify if regulations comply with statutes across multiple states.

CRITICAL REQUIREMENTS:
1. You MUST cite specific statutory authority for EVERY claim you make.
2. Citations must include: document name, section identifier (if available), and page numbers.
3. If you cannot find statutory authority for a question, clearly state this limitation.
4. Never make claims without supporting evidence from the provided legal texts.
5. When comparing across states, clearly attribute each provision to its state."""

    def __init__(self, opensearch_client, bedrock_client, model_id: str, embedding_model_id: str):
        self.os_client = opensearch_client
        self.bedrock = bedrock_client
        self.model_id = model_id
        self.embedding_model_id = embedding_model_id

    def execute(
        self,
        query: str,
        *,
        filter_state: str | None = None,
        filter_agency_type: str | None = None,
        filter_states: list[str] | None = None,
        history: list[dict] | None = None,
        top_k: int = 5,
    ) -> SearchResult:
        """Execute a search query and generate a cited response."""
        from backend.agents._search_helpers import (
            hybrid_search, format_context, call_llm,
        )

        results = hybrid_search(
            self.os_client, self.bedrock, self.embedding_model_id,
            query, top_k=top_k,
            filter_state=filter_state,
            filter_agency_type=filter_agency_type,
            filter_states=filter_states,
        )

        context = format_context(results)

        user_message = f"""Based on the following legal documents, please answer the user's question.
Remember: You MUST cite specific statutory authority for every claim.

RETRIEVED LEGAL CONTEXT:
{context}

USER QUESTION: {query}

Provide a clear, well-cited answer. If the context doesn't contain relevant information, clearly state this."""

        messages = []
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": [{"text": user_message}]})

        answer = call_llm(
            self.bedrock, self.model_id,
            system_prompt=self.SYSTEM_PROMPT,
            messages=messages,
        )

        citations = [
            {
                "document": r["source_document"],
                "section": r.get("section_identifier"),
                "pages": r["page_numbers"],
                "statute_codes": r.get("statute_codes", []),
                "relevance": round(r["score"], 3),
                "state": r.get("state", "MS"),
                "agency_type": r.get("agency_type", ""),
            }
            for r in results
        ]

        return SearchResult(
            answer=answer,
            citations=citations,
            search_results_count=len(results),
        )
