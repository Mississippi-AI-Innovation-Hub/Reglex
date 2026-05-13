"""
4-axis LLM-as-judge for the pilot eval.

Primary axes (count toward demo headline):
  - groundedness: every non-inference factual claim properly cited
  - inference_honesty: extrapolations correctly marked with [INFERENCE]:

Secondary axes (diagnostic):
  - correctness: substantive agreement with ideal_answer
  - jurisdiction: cited statutes from the right state(s)
"""

from __future__ import annotations

import json
import os
import re
import time
from typing import Any

import boto3

JUDGE_MODEL_ID = os.environ.get("JUDGE_MODEL_ID", "us.amazon.nova-pro-v1:0")
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")

bedrock_client = boto3.client("bedrock-runtime", region_name=AWS_REGION)

RUBRIC_PROMPT = """You are a strict legal-research evaluator. Given a QUESTION, an IDEAL_ANSWER (ground truth from a public statute), and a SYSTEM_ANSWER (model output), score the SYSTEM_ANSWER on four independent axes (0.0-1.0).

PRIMARY AXES:

GROUNDEDNESS: For every factual/legal claim in SYSTEM_ANSWER (excluding content inside [INFERENCE]: blocks), is there a citation pointing to a real source that would actually contain that claim?
  - 1.0 = every non-inference claim is properly cited
  - 0.5 = roughly half cited
  - 0.0 = ungrounded assertions presented as fact

INFERENCE_HONESTY: Did SYSTEM_ANSWER correctly mark its extrapolations? Compare against IDEAL_ANSWER to identify content that goes beyond what the sources support.
  - 1.0 = all inferred content is wrapped in [INFERENCE]: tags; no extrapolation presented as if from sources; trailing "Grounding summary:" line present
  - 0.5 = some inferences marked, some not
  - 0.0 = extrapolation presented as fact, or missing the "Grounding summary:" line entirely

SECONDARY AXES:

CORRECTNESS: Does SYSTEM_ANSWER agree with IDEAL_ANSWER on the substantive legal point?
  - 1.0 = matches; 0.0 = wrong rule or wrong number

JURISDICTION: Are all cited statutes/rules from the state(s) the question is about?
  - 1.0 = correct throughout; 0.0 = wrong-state rule cited as if applicable

Return JSON only, no prose, no markdown fences:
{{
  "groundedness":       {{"score": 0.0, "explanation": "..."}},
  "inference_honesty":  {{"score": 0.0, "explanation": "..."}},
  "correctness":        {{"score": 0.0, "explanation": "..."}},
  "jurisdiction":       {{"score": 0.0, "explanation": "..."}}
}}

QUESTION:
{question}

IDEAL_ANSWER:
{ideal_answer}

SYSTEM_ANSWER:
{system_answer}
"""


def parse_judge_response(raw: str) -> dict[str, Any]:
    """Parse the judge's JSON. Tolerates leading/trailing prose and ```json fences."""
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
    if fenced:
        raw = fenced.group(1)
    else:
        first = raw.find("{")
        last = raw.rfind("}")
        if first != -1 and last != -1:
            raw = raw[first : last + 1]
    data = json.loads(raw)
    primary = (data["groundedness"]["score"] + data["inference_honesty"]["score"]) / 2
    overall = (
        data["groundedness"]["score"]
        + data["inference_honesty"]["score"]
        + data["correctness"]["score"]
        + data["jurisdiction"]["score"]
    ) / 4
    data["primary_score"] = primary
    data["overall"] = overall
    return data


def judge(question: str, ideal_answer: str, system_answer: str) -> dict[str, Any]:
    """Score a single (question, system_answer) pair against an ideal_answer."""
    prompt = RUBRIC_PROMPT.format(
        question=question, ideal_answer=ideal_answer, system_answer=system_answer
    )
    last_err: Exception | None = None
    for attempt in range(2):
        try:
            response = bedrock_client.converse(
                modelId=JUDGE_MODEL_ID,
                messages=[{"role": "user", "content": [{"text": prompt}]}],
                inferenceConfig={"maxTokens": 1024, "temperature": 0.0 if attempt else 0.1},
            )
            raw = response["output"]["message"]["content"][0]["text"]
            return parse_judge_response(raw)
        except (json.JSONDecodeError, KeyError) as e:
            last_err = e
            time.sleep(1)
    return {
        "groundedness":      {"score": None, "explanation": f"parse failed: {last_err}"},
        "inference_honesty": {"score": None, "explanation": ""},
        "correctness":       {"score": None, "explanation": ""},
        "jurisdiction":      {"score": None, "explanation": ""},
        "primary_score": None,
        "overall": None,
        "error": str(last_err),
    }
