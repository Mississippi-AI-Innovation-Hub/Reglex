"""
Retry ingestion for documents that failed or weren't processed.

Identifies missing docs by comparing S3 contents against the progress file,
then removes them from failed_keys and re-runs the pipeline for just those docs.

Usage:
    AWS_PROFILE=<your-aws-profile> python retry_failed.py --index multistate-phase2-legal
"""

import argparse
import json
import os
import sys

from aws_session import AWSSession
from index_manager import IndexManager, PHASE1_INDEX, PHASE2_INDEX
from models import IngestionProgress
from pipeline import IngestionPipeline, _progress_file


def find_missing(session, s3_bucket, s3_prefix, progress_file):
    """Compare S3 contents against progress file to find missing docs."""
    s3 = session.client("s3")

    # Load progress
    completed = set()
    failed = set()
    if os.path.exists(progress_file):
        with open(progress_file) as f:
            data = json.load(f)
            completed = set(data.get("completed_keys", []))
            failed = set(data.get("failed_keys", []))

    # List all PDFs in S3
    paginator = s3.get_paginator("list_objects_v2")
    all_keys = set()
    for page in paginator.paginate(Bucket=s3_bucket, Prefix=s3_prefix):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            if key.lower().endswith(".pdf") and "proposal" not in key.lower() and ".DS_Store" not in key:
                all_keys.add(key)

    missing = all_keys - completed
    return {
        "all": all_keys,
        "completed": completed,
        "failed": failed,
        "missing": missing,
    }


def main():
    parser = argparse.ArgumentParser(description="Retry failed/missing document ingestion")
    parser.add_argument("--index", default=PHASE2_INDEX, help="OpenSearch index name")
    parser.add_argument("--s3-bucket", default="ms-sos-legal-documents")
    parser.add_argument("--s3-prefix", default="crawled-documents")
    parser.add_argument("--profile", default="<your-aws-profile>", help="AWS SSO profile")
    parser.add_argument("--opensearch-endpoint", required=True, help="OpenSearch endpoint URL")
    parser.add_argument("--dry-run", action="store_true", help="Just list missing docs, don't process")

    args = parser.parse_args()

    session = AWSSession(profile=args.profile)
    session.ensure_valid()

    progress_file = _progress_file(args.index)

    status = find_missing(session, args.s3_bucket, args.s3_prefix, progress_file)

    print("\n" + "=" * 60)
    print("RETRY STATUS — %s" % args.index)
    print("=" * 60)
    print("Total PDFs in S3: %d" % len(status["all"]))
    print("Already completed: %d" % len(status["completed"]))
    print("Previously failed: %d" % len(status["failed"]))
    print("Missing (will retry): %d" % len(status["missing"]))
    print()

    if not status["missing"]:
        print("Nothing to retry — all docs are completed.")
        return

    print("Missing documents:")
    for key in sorted(status["missing"]):
        print("  - %s" % key)

    if args.dry_run:
        print("\nDry run — not processing.")
        return

    # Remove missing keys from failed_keys so the pipeline retries them
    if os.path.exists(progress_file):
        with open(progress_file) as f:
            data = json.load(f)
        # Keep completed, remove from failed
        data["failed_keys"] = [k for k in data.get("failed_keys", []) if k not in status["missing"]]
        with open(progress_file, "w") as f:
            json.dump(data, f, indent=2, default=str)
        print("\nCleared %d keys from failed_keys for retry." % len(status["missing"]))

    # Now run the pipeline — it will only process docs not in completed_keys
    index_mgr = IndexManager(session, args.opensearch_endpoint)

    pipeline = IngestionPipeline(
        session=session,
        index_manager=index_mgr,
        index_name=args.index,
        s3_bucket=args.s3_bucket,
        s3_prefix=args.s3_prefix,
    )

    pipeline.run()


if __name__ == "__main__":
    main()
