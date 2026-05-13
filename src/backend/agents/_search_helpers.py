"""
Shared search and LLM helpers used by all agents.

Centralizes hybrid search execution, context formatting, and LLM calls
so agents stay focused on their domain logic.
"""

from __future__ import annotations

import json
from typing import Any


def get_embedding(bedrock_client, embedding_model_id: str, text: str) -> list[float]:
    """Generate embedding using Bedrock Titan."""
    body = json.dumps({"inputText": text, "dimensions": 1024, "normalize": True})
    response = bedrock_client.invoke_model(
        modelId=embedding_model_id,
        body=body,
        contentType="application/json",
        accept="application/json",
    )
    return json.loads(response["body"].read())["embedding"]


def hybrid_search(
    os_client,
    bedrock_client,
    embedding_model_id: str,
    query: str,
    *,
    index: str = "",
    top_k: int = 5,
    filter_state: str | None = None,
    filter_agency_type: str | None = None,
    filter_states: list[str] | None = None,
) -> list[dict]:
    """
    Execute hybrid search (kNN + BM25 + RRF) against OpenSearch.

    This mirrors the logic in vector_store_opensearch.py but works with
    raw opensearch-py clients (as used in Lambda).
    """
    index = index or "ms-legal-abstracts"
    candidate_pool = top_k * 3
    query_embedding = get_embedding(bedrock_client, embedding_model_id, query)

    # Build filters (use .keyword sub-field since main fields are text type)
    filters = []
    if filter_state:
        filters.append({"term": {"state.keyword": filter_state}})
    if filter_agency_type:
        filters.append({"term": {"agency_type.keyword": filter_agency_type}})
    if filter_states:
        filters.append({"terms": {"state.keyword": filter_states}})

    # kNN search
    knn_query: dict[str, Any] = {
        "size": candidate_pool,
        "query": {
            "knn": {
                "embedding_vector": {
                    "vector": query_embedding,
                    "k": candidate_pool,
                }
            }
        },
    }
    if filters:
        knn_query["query"] = {
            "bool": {"must": [knn_query["query"]], "filter": filters}
        }
    knn_resp = os_client.search(index=index, body=knn_query)
    knn_hits = knn_resp["hits"]["hits"]

    # BM25 search
    bm25_query: dict[str, Any] = {
        "size": candidate_pool,
        "query": {
            "bool": {
                "should": [
                    {"match": {"statute_codes": {"query": query, "boost": 4.0}}},
                    {"match": {"statutory_authority_references": {"query": query, "boost": 3.5}}},
                    {"match": {"section_identifier": {"query": query, "boost": 3.0}}},
                    {"match": {"abstract_text": {"query": query, "boost": 2.0}}},
                    {"match": {"core_rule": {"query": query, "boost": 2.0}}},
                    {"match": {"original_text": {"query": query, "boost": 1.5}}},
                    {"match": {"compliance_requirements": {"query": query, "boost": 1.5}}},
                    {"match": {"testing_requirements": {"query": query, "boost": 1.5}}},
                    {"match": {"reciprocity_provisions": {"query": query, "boost": 1.5}}},
                    {"match": {"legal_entities": {"query": query, "boost": 1.0}}},
                ],
                "minimum_should_match": 1,
            }
        },
    }
    if filters:
        bm25_query["query"]["bool"]["filter"] = filters
    bm25_resp = os_client.search(index=index, body=bm25_query)
    bm25_hits = bm25_resp["hits"]["hits"]

    # RRF merge
    merged = _rrf_merge(knn_hits, bm25_hits, top_k)

    return merged


def _rrf_merge(knn_hits: list, bm25_hits: list, top_k: int, rrf_k: int = 60) -> list[dict]:
    """Reciprocal Rank Fusion merge of kNN and BM25 results."""
    scores: dict[str, dict] = {}

    for rank, hit in enumerate(knn_hits):
        doc_id = hit["_id"]
        scores[doc_id] = {
            "rrf_score": 1.0 / (rrf_k + rank + 1),
            "source": hit["_source"],
        }

    for rank, hit in enumerate(bm25_hits):
        doc_id = hit["_id"]
        increment = 1.0 / (rrf_k + rank + 1)
        if doc_id in scores:
            scores[doc_id]["rrf_score"] += increment
        else:
            scores[doc_id] = {"rrf_score": increment, "source": hit["_source"]}

    ranked = sorted(scores.items(), key=lambda x: x[1]["rrf_score"], reverse=True)

    results = []
    for doc_id, data in ranked[:top_k]:
        src = data["source"]
        results.append({
            "abstract_text": src.get("abstract_text", ""),
            "core_rule": src.get("core_rule", ""),
            "source_document": src.get("source_document", ""),
            "page_numbers": src.get("page_numbers", []),
            "section_identifier": src.get("section_identifier"),
            "statute_codes": src.get("statute_codes", []),
            "original_text": (src.get("original_text") or "")[:2000],
            "score": data["rrf_score"],
            "state": src.get("state", "MS"),
            "agency_type": src.get("agency_type", ""),
            "agency_name": src.get("agency_name", ""),
            "fee_amounts": src.get("fee_amounts", []),
            "license_categories": src.get("license_categories", []),
            "testing_requirements": src.get("testing_requirements"),
            "statutory_authority_references": src.get("statutory_authority_references", []),
            "reciprocity_provisions": src.get("reciprocity_provisions"),
        })

    return results


def format_context(results: list[dict]) -> str:
    """Format search results into context for LLM prompt."""
    if not results:
        return "No relevant legal documents found for this query."

    parts = []
    for r in results:
        pages = ", ".join(str(p) for p in r.get("page_numbers", []))
        section = r.get("section_identifier") or "N/A"
        state = r.get("state", "MS")
        statutes = ", ".join(r.get("statute_codes", [])) or "None identified"

        parts.append(f"""---
STATE: {state}
SOURCE: {r['source_document']} (Section: {section}, Pages: {pages})
RELEVANCE SCORE: {r['score']:.4f}
STATUTE CODES: {statutes}

SUMMARY: {r['abstract_text']}

CORE RULE: {r.get('core_rule', 'N/A')}

ORIGINAL TEXT (for precise citation):
{r.get('original_text', '')}
---""")

    return "\n".join(parts)


def _normalize_messages(messages: list[dict]) -> list[dict]:
    """Normalize message content to Bedrock Converse format.

    Frontend sends: {"role": "user", "content": "plain string"}
    Bedrock expects: {"role": "user", "content": [{"text": "plain string"}]}
    """
    normalized = []
    for msg in messages:
        content = msg.get("content", "")
        if isinstance(content, str):
            normalized.append({"role": msg["role"], "content": [{"text": content}]})
        else:
            normalized.append(msg)
    return normalized


def call_llm(
    bedrock_client,
    model_id: str,
    *,
    system_prompt: str,
    messages: list[dict],
    max_tokens: int = 4096,
    temperature: float = 0.1,
) -> str:
    """Call Bedrock LLM via Converse API (model-agnostic)."""
    response = bedrock_client.converse(
        modelId=model_id,
        system=[{"text": system_prompt}],
        messages=_normalize_messages(messages),
        inferenceConfig={
            "maxTokens": max_tokens,
            "temperature": temperature,
            "topP": 0.9,
        },
    )
    return response["output"]["message"]["content"][0]["text"]
