"""
Document URL handler — generates presigned S3 URLs for PDF viewing.

Refactored from docs_lamda.py with enhanced support for multi-state documents.
"""

from __future__ import annotations

import json
import os

import boto3

S3_BUCKET = os.environ.get("S3_BUCKET", "ms-sos-legal-documents")
S3_PREFIX = os.environ.get("S3_PREFIX", "source-documents")
URL_EXPIRATION = int(os.environ.get("URL_EXPIRATION", "300"))  # 5 minutes

s3_client = boto3.client("s3")


def lambda_handler(event, context):
    """Generate presigned URL for a document in S3."""
    try:
        if "body" in event:
            body = json.loads(event["body"]) if isinstance(event["body"], str) else event["body"]
        else:
            body = event

        filename = body.get("filename", "")
        if not filename:
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "filename is required"}),
            }

        # Support state-prefixed paths: "TN/dental/document.pdf"
        # or plain filenames: "document.pdf"
        if "/" in filename:
            s3_key = f"crawled-documents/{filename}"
        else:
            s3_key = f"{S3_PREFIX}/{filename}"

        url = s3_client.generate_presigned_url(
            "get_object",
            Params={"Bucket": S3_BUCKET, "Key": s3_key},
            ExpiresIn=URL_EXPIRATION,
        )

        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
            },
            "body": json.dumps({"url": url}),
        }

    except Exception as e:
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"},
            "body": json.dumps({"error": str(e)}),
        }
