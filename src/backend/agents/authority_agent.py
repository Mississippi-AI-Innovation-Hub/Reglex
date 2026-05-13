"""
Statutory authority / ultra vires detection agent.

Use case: "Does the MS dental board have statutory authority to set this fee?"
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AuthorityResult:
    """Result from statutory authority analysis."""
    answer: str = ""
    citations: list[dict[str, Any]] = field(default_factory=list)
    authority_chain: list[dict[str, Any]] = field(default_factory=list)
    has_authority: bool | None = None


class AuthorityAgent:
    """
    Detects whether an agency has statutory authority for a given action.

    Searches for statutory authority references and rulemaking powers,
    then analyzes whether the action falls within that authority.
    """

    SYSTEM_PROMPT = """You are a legal research assistant specializing in statutory authority analysis.
Your task is to determine whether a state agency has the statutory authority to take a specific action.

REQUIREMENTS:
1. Identify the enabling statute that grants the agency rulemaking authority.
2. Analyze whether the specific action falls within that granted authority.
3. Note any limitations or restrictions on the agency's authority.
4. If the action appears to exceed statutory authority (ultra vires), explain why.
5. Trace the complete authority chain: statute -> delegation -> regulation.
6. Cite specific statutory provisions for every conclusion."""

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
        top_k: int = 10,
    ) -> AuthorityResult:
        """Analyze statutory authority for an agency action."""
        from backend.agents._search_helpers import hybrid_search, format_context, call_llm

        auth_query = f"statutory authority rulemaking power delegation {query}"

        results = hybrid_search(
            self.os_client, self.bedrock, self.embedding_model_id,
            auth_query, top_k=top_k,
            filter_state=filter_state,
            filter_agency_type=filter_agency_type,
        )

        context = format_context(results)

        # Extract authority chain
        authority_chain = []
        for r in results:
            if r.get("statutory_authority_references"):
                authority_chain.append({
                    "state": r.get("state", "MS"),
                    "authority_references": r.get("statutory_authority_references", []),
                    "document": r["source_document"],
                    "section": r.get("section_identifier", ""),
                    "core_rule": r.get("core_rule", ""),
                })

        user_message = f"""Analyze the statutory authority for the following question:

{context}

AUTHORITY CHAIN DATA:
{chr(10).join(f"- {ac['document']}: Authority refs: {ac['authority_references']}" for ac in authority_chain) if authority_chain else "No explicit statutory authority references found."}

USER QUESTION: {query}

Determine whether the agency has statutory authority. Trace the authority chain from enabling statute to the specific regulation in question."""

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

        return AuthorityResult(
            answer=answer,
            citations=citations,
            authority_chain=authority_chain,
        )
