"""
Reflection agent — citation verification and claim decomposition.

Inspired by Protege's Shepard's Citation Agent:
1. Extract all factual claims from an LLM response
2. Verify each claim has a supporting citation
3. Verify the cited text supports the claim
4. Flag unsupported claims with confidence score
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ClaimVerification:
    """Verification result for a single claim."""
    claim: str
    supported: bool
    confidence: float
    supporting_citation: str | None = None
    explanation: str = ""


@dataclass
class ReflectionResult:
    """Result from reflection/verification."""
    verified_claims: list[ClaimVerification] = field(default_factory=list)
    overall_confidence: float = 0.0
    unsupported_count: int = 0
    total_claims: int = 0


DECOMPOSITION_PROMPT = """Extract all factual claims from the following legal research response.
A "claim" is any statement of fact, rule, requirement, or legal conclusion.

<response>
{response}
</response>

Return a JSON array of claims:
[
    "Claim 1 text",
    "Claim 2 text",
    ...
]

Extract only factual/legal claims, not opinions or hedging language.
Return ONLY the JSON array."""

VERIFICATION_PROMPT = """Verify whether the following claim is supported by the provided source documents.

<claim>
{claim}
</claim>

<source_documents>
{context}
</source_documents>

Return a JSON object:
{{
    "supported": true or false,
    "confidence": 0.0 to 1.0,
    "supporting_citation": "The specific document and section that supports this claim, or null",
    "explanation": "Brief explanation of why this claim is or is not supported"
}}

Return ONLY the JSON object."""


class ReflectionAgent:
    """
    Verifies LLM responses by decomposing claims and checking citations.

    Used as a post-processing step after any agent generates a response.
    """

    def __init__(self, bedrock_client, model_id: str):
        self.bedrock = bedrock_client
        self.model_id = model_id

    def verify(
        self,
        response_text: str,
        search_results: list[dict[str, Any]],
    ) -> ReflectionResult:
        """
        Verify an LLM response against source documents.

        1. Decompose response into individual claims
        2. Verify each claim against the source documents
        3. Return verification results with confidence scores
        """
        # Step 1: Decompose claims
        claims = self._decompose_claims(response_text)

        if not claims:
            return ReflectionResult(overall_confidence=0.5, total_claims=0)

        # Build context from search results
        context = "\n\n".join(
            f"SOURCE: {r.get('source_document', 'Unknown')} "
            f"(Section: {r.get('section_identifier', 'N/A')}, "
            f"Pages: {r.get('page_numbers', [])})\n"
            f"{r.get('original_text', r.get('abstract_text', ''))[:1500]}"
            for r in search_results
        )

        # Step 2: Verify each claim
        verifications = []
        for claim in claims:
            v = self._verify_claim(claim, context)
            verifications.append(v)

        unsupported = sum(1 for v in verifications if not v.supported)
        total = len(verifications)
        avg_confidence = (
            sum(v.confidence for v in verifications) / total
            if total > 0 else 0.0
        )

        return ReflectionResult(
            verified_claims=verifications,
            overall_confidence=round(avg_confidence, 3),
            unsupported_count=unsupported,
            total_claims=total,
        )

    def _decompose_claims(self, response_text: str) -> list[str]:
        """Extract factual claims from a response."""
        prompt = DECOMPOSITION_PROMPT.format(response=response_text)

        response = self.bedrock.converse(
            modelId=self.model_id,
            messages=[{"role": "user", "content": [{"text": prompt}]}],
            inferenceConfig={"maxTokens": 2048, "temperature": 0.0},
        )

        raw = response["output"]["message"]["content"][0]["text"]
        return self._parse_json_array(raw)

    def _verify_claim(self, claim: str, context: str) -> ClaimVerification:
        """Verify a single claim against source context."""
        prompt = VERIFICATION_PROMPT.format(claim=claim, context=context[:8000])

        response = self.bedrock.converse(
            modelId=self.model_id,
            messages=[{"role": "user", "content": [{"text": prompt}]}],
            inferenceConfig={"maxTokens": 1024, "temperature": 0.0},
        )

        raw = response["output"]["message"]["content"][0]["text"]
        parsed = self._parse_json_object(raw)

        return ClaimVerification(
            claim=claim,
            supported=bool(parsed.get("supported", False)),
            confidence=float(parsed.get("confidence", 0.0)),
            supporting_citation=parsed.get("supporting_citation"),
            explanation=parsed.get("explanation", ""),
        )

    @staticmethod
    def _parse_json_array(raw: str) -> list[str]:
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[-1] if "\n" in cleaned else cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()
        try:
            result = json.loads(cleaned)
            return result if isinstance(result, list) else []
        except json.JSONDecodeError:
            return []

    @staticmethod
    def _parse_json_object(raw: str) -> dict:
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[-1] if "\n" in cleaned else cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            return {"supported": False, "confidence": 0.0, "explanation": "Parse error"}
