"""
Orchestrator — routes queries to the appropriate agent based on intent.

Flow:
1. QueryClassifier detects intent + extracts parameters
2. Orchestrator routes to the appropriate agent
3. Agent executes search/analysis
4. ReflectionAgent verifies citations (optional)
5. Returns structured result
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from typing import Any

import boto3
from opensearchpy import OpenSearch, RequestsHttpConnection
from requests_aws4auth import AWS4Auth

from backend.agents.query_classifier import QueryClassifier, QueryIntent, ClassificationResult
from backend.agents.search_agent import SearchAgent
from backend.agents.comparison_agent import ComparisonAgent
from backend.agents.term_frequency_agent import TermFrequencyAgent
from backend.agents.fee_analysis_agent import FeeAnalysisAgent
from backend.agents.reciprocity_agent import ReciprocityAgent
from backend.agents.authority_agent import AuthorityAgent
from backend.agents.reflection_agent import ReflectionAgent


@dataclass
class OrchestratorResponse:
    """Unified response from the orchestrator."""
    answer: str = ""
    citations: list[dict[str, Any]] = field(default_factory=list)
    intent: str = "general_research"
    confidence: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)
    verification: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        if d.get("verification") is None:
            d.pop("verification", None)
        return d


# Default states when user doesn't specify
DEFAULT_COMPARISON_STATES = ["MS", "AL", "LA", "TN", "AR", "GA", "TX"]


class Orchestrator:
    """
    Routes queries to specialized agents based on classified intent.

    Initializes AWS clients once and passes them to agents.
    """

    def __init__(
        self,
        opensearch_endpoint: str,
        opensearch_index: str,
        bedrock_model_id: str,
        bedrock_embedding_model_id: str,
        region: str = "us-east-1",
        enable_reflection: bool = False,
    ):
        self.index = opensearch_index
        self.model_id = bedrock_model_id
        self.embedding_model_id = bedrock_embedding_model_id
        self.enable_reflection = enable_reflection

        # Initialize AWS clients
        credentials = boto3.Session().get_credentials()
        awsauth = AWS4Auth(
            credentials.access_key,
            credentials.secret_key,
            region,
            "es",
            session_token=credentials.token,
        )

        host = opensearch_endpoint.replace("https://", "").replace("http://", "")
        self.os_client = OpenSearch(
            hosts=[{"host": host, "port": 443}],
            http_auth=awsauth,
            use_ssl=True,
            verify_certs=True,
            connection_class=RequestsHttpConnection,
            timeout=30,
        )

        self.bedrock = boto3.client("bedrock-runtime", region_name=region)

        # Initialize classifier
        self.classifier = QueryClassifier(
            bedrock_model_id=bedrock_model_id,
            region=region,
        )

        # Initialize agents
        agent_kwargs = dict(
            opensearch_client=self.os_client,
            bedrock_client=self.bedrock,
            model_id=self.model_id,
            embedding_model_id=self.embedding_model_id,
        )
        self.search_agent = SearchAgent(**agent_kwargs)
        self.comparison_agent = ComparisonAgent(**agent_kwargs)
        self.term_freq_agent = TermFrequencyAgent(**agent_kwargs)
        self.fee_agent = FeeAnalysisAgent(**agent_kwargs)
        self.reciprocity_agent = ReciprocityAgent(**agent_kwargs)
        self.authority_agent = AuthorityAgent(**agent_kwargs)

        if self.enable_reflection:
            self.reflection_agent = ReflectionAgent(
                bedrock_client=self.bedrock,
                model_id=self.model_id,
            )

    def process(
        self,
        query: str,
        *,
        filters: dict[str, Any] | None = None,
        history: list[dict] | None = None,
        mode: str | None = None,
    ) -> OrchestratorResponse:
        """
        Process a user query through the full orchestrator pipeline.

        Args:
            query: The user's question
            filters: Optional filters (state, agency_type, states)
            history: Conversation history for multi-turn
            mode: Override mode ("research", "compare", "count")
        """
        filters = filters or {}

        # Step 1: Classify intent
        classification = self.classifier.classify(query)

        # Allow mode override
        if mode == "compare":
            classification.intent = QueryIntent.FEE_BENCHMARKING
        elif mode == "count":
            classification.intent = QueryIntent.TERM_FREQUENCY

        # Merge user-provided filters with classified parameters
        states = filters.get("states") or classification.extracted_states
        agency_type = filters.get("agency_type") or (
            classification.extracted_agency_types[0]
            if classification.extracted_agency_types else None
        )
        filter_state = filters.get("state")

        # Step 2: Route to agent
        result = self._route(
            classification, query,
            states=states,
            agency_type=agency_type,
            filter_state=filter_state,
            history=history,
        )

        # Step 3: Optional reflection/verification
        verification = None
        if self.enable_reflection and result.answer:
            # Collect raw search results for verification (from citations)
            search_data = [
                {"source_document": c.get("document", ""), "section_identifier": c.get("section"), "page_numbers": c.get("pages", [])}
                for c in result.citations
            ]
            ref_result = self.reflection_agent.verify(result.answer, search_data)
            verification = {
                "overall_confidence": ref_result.overall_confidence,
                "total_claims": ref_result.total_claims,
                "unsupported_count": ref_result.unsupported_count,
                "claims": [asdict(v) for v in ref_result.verified_claims],
            }

        return OrchestratorResponse(
            answer=result.answer,
            citations=result.citations,
            intent=classification.intent.value,
            confidence=classification.confidence,
            metadata=getattr(result, "metadata", {}) if hasattr(result, "metadata") else self._extract_metadata(result),
            verification=verification,
        )

    def _route(
        self,
        classification: ClassificationResult,
        query: str,
        *,
        states: list[str],
        agency_type: str | None,
        filter_state: str | None,
        history: list[dict] | None,
    ) -> Any:
        """Route to the appropriate agent based on intent."""
        intent = classification.intent

        # Comparison-type intents need multiple states
        comparison_intents = {
            QueryIntent.FEE_BENCHMARKING,
            QueryIntent.LICENSE_CATEGORY_COMPARE,
            QueryIntent.TESTING_REQUIREMENTS,
        }

        if intent == QueryIntent.FEE_COMPARISON or intent == QueryIntent.FEE_BENCHMARKING:
            return self.fee_agent.execute(
                query,
                states=states or (DEFAULT_COMPARISON_STATES if intent == QueryIntent.FEE_BENCHMARKING else None),
                agency_type=agency_type,
            )

        if intent == QueryIntent.TERM_FREQUENCY:
            return self.term_freq_agent.execute(
                query,
                terms=classification.extracted_terms,
                filter_state=filter_state or (states[0] if len(states) == 1 else None),
                filter_agency_type=agency_type,
                filter_states=states if len(states) > 1 else None,
            )

        if intent == QueryIntent.LICENSING_RECIPROCITY:
            return self.reciprocity_agent.execute(
                query,
                states=states or DEFAULT_COMPARISON_STATES,
                agency_type=agency_type,
            )

        if intent == QueryIntent.STATUTORY_AUTHORITY:
            return self.authority_agent.execute(
                query,
                filter_state=filter_state or (states[0] if states else None),
                filter_agency_type=agency_type,
            )

        if intent in comparison_intents:
            return self.comparison_agent.execute(
                query,
                states=states or DEFAULT_COMPARISON_STATES,
                agency_type=agency_type,
            )

        if intent == QueryIntent.AMENDMENT_HISTORY:
            return self.comparison_agent.execute(
                query,
                states=states or (["MS"] if not states else states),
                agency_type=agency_type,
            )

        # Default: general research
        return self.search_agent.execute(
            query,
            filter_state=filter_state or (states[0] if len(states) == 1 else None),
            filter_agency_type=agency_type,
            filter_states=states if len(states) > 1 else None,
            history=history,
        )

    @staticmethod
    def _extract_metadata(result: Any) -> dict[str, Any]:
        """Extract structured metadata from agent-specific result types."""
        metadata: dict[str, Any] = {}
        if hasattr(result, "comparison_table") and result.comparison_table:
            metadata["comparison_table"] = result.comparison_table
        if hasattr(result, "states_compared") and result.states_compared:
            metadata["states_compared"] = result.states_compared
        if hasattr(result, "frequency_data") and result.frequency_data:
            metadata["frequency_data"] = result.frequency_data
            metadata["total_count"] = getattr(result, "total_count", 0)
        if hasattr(result, "fee_table") and result.fee_table:
            metadata["fee_table"] = result.fee_table
            metadata["states_analyzed"] = getattr(result, "states_analyzed", [])
        if hasattr(result, "reciprocity_data") and result.reciprocity_data:
            metadata["reciprocity_data"] = result.reciprocity_data
        if hasattr(result, "authority_chain") and result.authority_chain:
            metadata["authority_chain"] = result.authority_chain
            metadata["has_authority"] = getattr(result, "has_authority", None)
        return metadata
