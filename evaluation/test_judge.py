"""Unit test for evals.judge — uses fake Bedrock responses, no network."""
from unittest.mock import patch, MagicMock
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from evals.judge import judge, parse_judge_response


def test_parse_judge_response_well_formed():
    raw = json.dumps({
        "groundedness":      {"score": 0.9, "explanation": "all cited"},
        "inference_honesty": {"score": 0.8, "explanation": "one missed"},
        "correctness":       {"score": 0.7, "explanation": "minor wording"},
        "jurisdiction":      {"score": 1.0, "explanation": "MS only"},
    })
    parsed = parse_judge_response(raw)
    assert parsed["groundedness"]["score"] == 0.9
    assert parsed["primary_score"] == (0.9 + 0.8) / 2
    assert parsed["overall"] == (0.9 + 0.8 + 0.7 + 1.0) / 4


def test_parse_judge_response_with_extra_text():
    raw = "Here is my evaluation:\n```json\n" + json.dumps({
        "groundedness":      {"score": 0.5, "explanation": ""},
        "inference_honesty": {"score": 0.5, "explanation": ""},
        "correctness":       {"score": 0.5, "explanation": ""},
        "jurisdiction":      {"score": 0.5, "explanation": ""},
    }) + "\n```"
    parsed = parse_judge_response(raw)
    assert parsed["primary_score"] == 0.5


def test_judge_calls_bedrock_with_rubric():
    fake_response = {
        "output": {"message": {"content": [{"text": json.dumps({
            "groundedness":      {"score": 1.0, "explanation": ""},
            "inference_honesty": {"score": 1.0, "explanation": ""},
            "correctness":       {"score": 1.0, "explanation": ""},
            "jurisdiction":      {"score": 1.0, "explanation": ""},
        })}]}}
    }
    with patch("evals.judge.bedrock_client") as mock_client:
        mock_client.converse.return_value = fake_response
        result = judge(
            question="What is the MS notary fee?",
            ideal_answer="$25 per Miss. Code Ann. § 25-33-3",
            system_answer="The fee is $25 (Source: 25-33-3.pdf, p.1).\n\nGrounding summary: 1 grounded, 0 inferred",
        )
    assert result["overall"] == 1.0
    args, kwargs = mock_client.converse.call_args
    rubric_prompt = kwargs["messages"][0]["content"][0]["text"]
    assert "GROUNDEDNESS" in rubric_prompt
    assert "INFERENCE_HONESTY" in rubric_prompt
    assert "JURISDICTION" in rubric_prompt


if __name__ == "__main__":
    test_parse_judge_response_well_formed()
    test_parse_judge_response_with_extra_text()
    test_judge_calls_bedrock_with_rubric()
    print("All judge tests passed.")
