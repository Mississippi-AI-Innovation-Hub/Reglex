"""
Crawl scheduler — EventBridge integration for automated crawl runs.

Provides helpers for scheduling crawls via AWS EventBridge rules
and Step Functions execution.
"""

from __future__ import annotations

import json
from dataclasses import dataclass


@dataclass
class ScheduleConfig:
    """Configuration for scheduled crawl runs."""
    rule_name: str = "sos-regulatory-crawl-weekly"
    schedule_expression: str = "rate(7 days)"  # Weekly crawl
    state_machine_arn: str = ""
    enabled: bool = True


def create_eventbridge_rule_params(config: ScheduleConfig) -> dict:
    """
    Generate the parameters for creating an EventBridge rule.

    This is used by the deployment/IaC scripts — not called at runtime.
    The actual EventBridge rule is created via CloudFormation or CDK.
    """
    return {
        "Name": config.rule_name,
        "ScheduleExpression": config.schedule_expression,
        "State": "ENABLED" if config.enabled else "DISABLED",
        "Description": "Weekly crawl of regulatory documents across 7 states x 3 agency types",
    }


def create_step_function_input(
    states: list[str] | None = None,
    agency_types: list[str] | None = None,
) -> str:
    """
    Generate the input JSON for a Step Functions crawl execution.

    When no filters are provided, all 21 targets are crawled.
    """
    input_data = {}
    if states:
        input_data["states"] = states
    if agency_types:
        input_data["agency_types"] = agency_types
    return json.dumps(input_data)


def lambda_handler_scheduled_crawl(event: dict, context: object) -> dict:
    """
    Lambda handler invoked by EventBridge for scheduled crawls.

    This is a thin wrapper that:
    1. Parses the schedule event
    2. Runs the crawl pipeline
    3. Saves results to S3 + generates manifest
    """
    from backend.crawlers.run_crawl import run_crawl

    states = event.get("states")
    agency_types = event.get("agency_types")

    result = run_crawl(
        states=states,
        agency_types=agency_types,
        dest_root="/tmp/crawled_documents",
        upload_to_s3=True,
    )

    return {
        "statusCode": 200,
        "body": json.dumps({
            "crawl_id": result.get("crawl_id", ""),
            "total_downloaded": result.get("total_downloaded", 0),
            "total_errors": result.get("total_errors", 0),
        }),
    }
