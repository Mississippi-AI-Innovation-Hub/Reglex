"""
Query classifier — detects user intent and extracts parameters.

Uses an LLM call to classify queries into one of 9 intent categories
derived from Colby's 8 regulatory use cases + general research.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import boto3


class QueryIntent(str, Enum):
    """The 9 intent categories for regulatory queries."""
    FEE_COMPARISON = "fee_comparison"
    TERM_FREQUENCY = "term_frequency"
    LICENSING_RECIPROCITY = "licensing_reciprocity"
    FEE_BENCHMARKING = "fee_benchmarking"
    AMENDMENT_HISTORY = "amendment_history"
    STATUTORY_AUTHORITY = "statutory_authority"
    LICENSE_CATEGORY_COMPARE = "license_category_compare"
    TESTING_REQUIREMENTS = "testing_requirements"
    GENERAL_RESEARCH = "general_research"


@dataclass
class ClassificationResult:
    """Result of query classification."""
    intent: QueryIntent
    confidence: float
    extracted_states: list[str] = field(default_factory=list)
    extracted_agency_types: list[str] = field(default_factory=list)
    extracted_terms: list[str] = field(default_factory=list)
    parameters: dict[str, Any] = field(default_factory=dict)


CLASSIFICATION_PROMPT = """You are a query classifier for a regulatory legal research system.
Classify the following user query into exactly one intent category and extract relevant parameters.

Intent categories:
1. fee_comparison — Comparing fines/fees vs statutory caps within a single state
2. term_frequency — Counting how many times a term appears with references
3. licensing_reciprocity — Out-of-state licensure reciprocity analysis
4. fee_benchmarking — Cross-state fee comparison
5. amendment_history — When a regulation was last amended/adopted
6. statutory_authority — Ultra vires detection (does agency have authority?)
7. license_category_compare — Comparing temporary license categories across states
8. testing_requirements — Exam requirement comparison across states
9. general_research — Catch-all for general regulatory questions

State codes: MS (Mississippi), AL (Alabama), LA (Louisiana), TN (Tennessee), AR (Arkansas), GA (Georgia), TX (Texas)
Agency types: medical, real_estate, dental

<user_query>
{query}
</user_query>

Respond with ONLY a JSON object:
{{
    "intent": "one of the 9 intent categories above",
    "confidence": 0.0 to 1.0,
    "states": ["list of state codes mentioned or implied, e.g. MS, TN"],
    "agency_types": ["list of agency types mentioned or implied"],
    "terms": ["key terms to search for"],
    "parameters": {{}}
}}
"""


class QueryClassifier:
    """Classifies user queries into intent categories using an LLM."""

    def __init__(self, bedrock_model_id: str = "", region: str = "us-east-1"):
        self.model_id = bedrock_model_id or "mistral.mistral-large-3-675b-instruct"
        self.client = boto3.client("bedrock-runtime", region_name=region)

    def classify(self, query: str) -> ClassificationResult:
        """Classify a user query into an intent with extracted parameters."""
        prompt = CLASSIFICATION_PROMPT.format(query=query)

        response = self.client.converse(
            modelId=self.model_id,
            messages=[{"role": "user", "content": [{"text": prompt}]}],
            inferenceConfig={"maxTokens": 1024, "temperature": 0.0, "topP": 0.9},
        )

        raw = response["output"]["message"]["content"][0]["text"]
        parsed = self._parse_response(raw)

        return ClassificationResult(
            intent=self._resolve_intent(parsed.get("intent", "general_research")),
            confidence=float(parsed.get("confidence", 0.5)),
            extracted_states=parsed.get("states", []),
            extracted_agency_types=parsed.get("agency_types", []),
            extracted_terms=parsed.get("terms", []),
            parameters=parsed.get("parameters", {}),
        )

    @staticmethod
    def _resolve_intent(raw: str) -> QueryIntent:
        """Resolve a raw intent string to a QueryIntent enum."""
        try:
            return QueryIntent(raw.lower().strip())
        except ValueError:
            return QueryIntent.GENERAL_RESEARCH

    @staticmethod
    def _parse_response(raw: str) -> dict:
        """Parse JSON from LLM response with error recovery."""
        cleaned = raw.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        if cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            return {"intent": "general_research", "confidence": 0.3}
