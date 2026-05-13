"""
Docs endpoint — returns a presigned S3 URL for a given document.

Handles both:
  - Phase 1 (flat): source-documents/{filename}
  - Phase 2 (hierarchical): crawled-documents/{STATE}/{agency_type}/{filename}

The frontend may pass state + agency_type to help locate the file.
If not provided, we try both locations and return whichever exists.
"""

import json
import boto3

s3 = boto3.client("s3")
BUCKET = "ms-sos-legal-documents"

PHASE1_PREFIX = "source-documents/"
PHASE2_PREFIX = "crawled-documents/"


def _object_exists(bucket, key):
    """Check if an S3 key exists (HEAD request)."""
    try:
        s3.head_object(Bucket=bucket, Key=key)
        return True
    except Exception:
        return False


def _find_key(filename, state=None, agency_type=None):
    """
    Find the correct S3 key for a filename.
    Tries hinted location first, then falls back to both phases.
    """
    candidates = []

    # Prefer Phase 2 path if state+agency provided
    if state and agency_type:
        candidates.append(f"{PHASE2_PREFIX}{state.upper()}/{agency_type.lower()}/{filename}")

    # Phase 2 with just state — try all 3 agency types
    if state and not agency_type:
        for agency in ("medical", "dental", "real_estate"):
            candidates.append(f"{PHASE2_PREFIX}{state.upper()}/{agency}/{filename}")

    # Phase 1 flat path
    candidates.append(f"{PHASE1_PREFIX}{filename}")

    # Last resort: search across all Phase 2 paths
    if not state:
        for st in ("MS", "AL", "AR", "GA", "LA", "TN", "TX"):
            for agency in ("medical", "dental", "real_estate"):
                candidates.append(f"{PHASE2_PREFIX}{st}/{agency}/{filename}")

    for key in candidates:
        if _object_exists(BUCKET, key):
            return key

    return None


def handler(event, context):
    # CORS preflight
    if event.get("httpMethod") == "OPTIONS":
        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Content-Type,Authorization,x-api-key",
                "Access-Control-Allow-Methods": "POST,OPTIONS",
            },
            "body": "",
        }

    try:
        # Handle both AWS_PROXY (body in event['body']) and non-proxy (body merged with event)
        raw_body = event.get("body")
        if isinstance(raw_body, str):
            body = json.loads(raw_body or "{}")
        elif isinstance(raw_body, dict):
            body = raw_body
        else:
            body = event  # non-proxy — body is the event itself

        filename = body.get("filename")
        if not filename:
            return {
                "statusCode": 400,
                "headers": {"Access-Control-Allow-Origin": "*"},
                "body": json.dumps({"error": "filename is required"}),
            }

        state = body.get("state")
        agency_type = body.get("agency_type")

        key = _find_key(filename, state=state, agency_type=agency_type)
        if not key:
            return {
                "statusCode": 404,
                "headers": {"Access-Control-Allow-Origin": "*"},
                "body": json.dumps({"error": f"Document not found: {filename}"}),
            }

        url = s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": BUCKET, "Key": key},
            ExpiresIn=300,
        )

        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
            },
            "body": json.dumps({"url": url, "key": key}),
        }

    except Exception as e:
        return {
            "statusCode": 500,
            "headers": {"Access-Control-Allow-Origin": "*"},
            "body": json.dumps({"error": str(e)}),
        }
