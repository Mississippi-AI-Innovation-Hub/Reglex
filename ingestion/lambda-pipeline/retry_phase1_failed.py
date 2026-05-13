"""
Retry the known-failed Phase 1 documents.

Usage:
    cd ingestion/lambda-pipeline
    AWS_PROFILE=<your-profile> python retry_phase1_failed.py

Configure the OpenSearch endpoint and S3 bucket via environment variables
or by editing the placeholders below before running in your own account.
"""
from __future__ import annotations

import os
import sys

from aws_session import AWSSession
from index_manager import IndexManager, PHASE1_INDEX
from lease import LeaseManager
from pipeline import IngestionPipeline

OPENSEARCH_ENDPOINT = os.getenv(
    "OPENSEARCH_ENDPOINT",
    "https://search-<your-domain>.<region>.es.amazonaws.com",
)
S3_BUCKET = os.getenv("S3_BUCKET", "<your-s3-bucket>")
S3_PREFIX = os.getenv("S3_PREFIX", "source-documents")

FAILED_KEYS = [
    "source-documents/00000051c.pdf",
    "source-documents/00000052c.pdf",
    "source-documents/00000053c.pdf",
]


def clear_failed_in_ledger(index_name: str, keys: list[str]) -> int:
    """Drop `keys` from ledger['failed'] so they become claimable again."""
    ledger = LeaseManager(index_name)
    cleared = 0
    with ledger._locked() as data:
        before = set(data.get("failed", []))
        kept = [k for k in data.get("failed", []) if k not in keys]
        data["failed"] = kept
        cleared = len(before) - len(kept)
    return cleared


def main() -> int:
    print("=" * 60)
    print("Phase 1 retry — 3 known failures")
    print("=" * 60)

    cleared = clear_failed_in_ledger(PHASE1_INDEX, FAILED_KEYS)
    print(f"Cleared {cleared} keys from ledger['failed'].")

    session = AWSSession(profile="<your-aws-profile>")
    session.ensure_valid()
    index_mgr = IndexManager(session, OPENSEARCH_ENDPOINT)

    pipeline = IngestionPipeline(
        session=session,
        index_manager=index_mgr,
        index_name=PHASE1_INDEX,
        s3_bucket=S3_BUCKET,
        s3_prefix=S3_PREFIX,
        state="MS",
        batch_size=len(FAILED_KEYS),
    )

    # Scope this run to the retry set — head_object resolves real S3 size,
    # confirms the keys still exist before the pipeline touches them.
    s3 = session.client("s3")

    def _retry_only_pdfs():
        out = []
        for key in FAILED_KEYS:
            head = s3.head_object(Bucket=S3_BUCKET, Key=key)
            out.append({
                "key": key,
                "filename": key.split("/")[-1],
                "size": head["ContentLength"],
                "state": "MS",
                "agency_type": "",
            })
        return out

    pipeline.list_pdfs = _retry_only_pdfs

    try:
        pipeline.run(max_docs=len(FAILED_KEYS))
    finally:
        try:
            pipeline.lease.release()
        except Exception:
            pass

    return 0


if __name__ == "__main__":
    sys.exit(main())
