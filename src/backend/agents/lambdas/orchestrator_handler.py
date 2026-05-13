"""
Unified Lambda entry point for the orchestrated multi-agent system.

Replaces the original lambda_handler.py with:
- Hybrid search (kNN + BM25 + RRF) instead of kNN-only
- Intent classification and agent routing
- State/agency filtering
- Multi-turn conversation history
- Structured metadata in response (comparison tables, frequency data, etc.)
"""

from __future__ import annotations

import json
import os

from backend.agents.orchestrator import Orchestrator


# Environment variables
OPENSEARCH_ENDPOINT = os.environ.get("OPENSEARCH_ENDPOINT", "")
OPENSEARCH_INDEX = os.environ.get("OPENSEARCH_INDEX", "ms-legal-abstracts")
BEDROCK_MODEL_ID = os.environ.get("BEDROCK_MODEL_ID", "mistral.mistral-large-3-675b-instruct")
BEDROCK_EMBEDDING_MODEL_ID = os.environ.get("BEDROCK_EMBEDDING_MODEL_ID", "amazon.titan-embed-text-v2:0")
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
ENABLE_REFLECTION = os.environ.get("ENABLE_REFLECTION", "false").lower() == "true"

# Initialize orchestrator (cold start — reused across invocations)
_orchestrator: Orchestrator | None = None


def _get_orchestrator() -> Orchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = Orchestrator(
            opensearch_endpoint=OPENSEARCH_ENDPOINT,
            opensearch_index=OPENSEARCH_INDEX,
            bedrock_model_id=BEDROCK_MODEL_ID,
            bedrock_embedding_model_id=BEDROCK_EMBEDDING_MODEL_ID,
            region=AWS_REGION,
            enable_reflection=ENABLE_REFLECTION,
        )
    return _orchestrator


def _cors_headers() -> dict:
    return {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Headers": "Content-Type,Authorization",
        "Access-Control-Allow-Methods": "POST,OPTIONS",
    }


def lambda_handler(event, context):
    """
    Main Lambda handler for the orchestrated API.

    Accepts:
        POST /api/chat     — Enhanced chat (backward compatible)
        POST /api/research  — Multi-step research with filters
        POST /api/compare   — Cross-jurisdiction comparison

    Request body:
        {
            "query": "user question",
            "filters": {"state": "MS", "agency_type": "medical", "states": ["MS", "TN"]},
            "history": [{"role": "user", "content": "..."}],
            "mode": "research" | "compare" | "count"
        }

    Response body:
        {
            "answer": "LLM response with citations",
            "citations": [...],
            "intent": "detected intent",
            "metadata": { comparison_table, frequency_data, fee_table, ... },
            "query": "original query"
        }
    """
    # Handle CORS preflight
    if event.get("httpMethod") == "OPTIONS":
        return {"statusCode": 200, "headers": _cors_headers(), "body": ""}

    try:
        # Parse request
        if "body" in event:
            body = json.loads(event["body"]) if isinstance(event["body"], str) else event["body"]
        else:
            body = event

        query = body.get("query", "")
        if not query:
            return {
                "statusCode": 400,
                "headers": _cors_headers(),
                "body": json.dumps({"error": "Query parameter is required"}),
            }

        filters = body.get("filters", {})
        history = body.get("history")
        mode = body.get("mode")

        # Process through orchestrator
        orchestrator = _get_orchestrator()
        result = orchestrator.process(
            query,
            filters=filters,
            history=history,
            mode=mode,
        )

        response_body = {
            "answer": result.answer,
            "citations": result.citations,
            "intent": result.intent,
            "metadata": result.metadata,
            "query": query,
        }

        if result.verification:
            response_body["verification"] = result.verification

        return {
            "statusCode": 200,
            "headers": _cors_headers(),
            "body": json.dumps(response_body),
        }

    except Exception as e:
        print(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            "statusCode": 500,
            "headers": _cors_headers(),
            "body": json.dumps({"error": str(e)}),
        }
