"""
CLI entrypoint for the multi-state regulatory document crawler.

Usage:
    python -m backend.crawlers.run_crawl                          # Crawl all 21 targets
    python -m backend.crawlers.run_crawl --state MS --state TN    # Specific states
    python -m backend.crawlers.run_crawl --agency medical         # Specific agency type
    python -m backend.crawlers.run_crawl --state TX --agency dental --dest ./output
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from backend.crawlers.base_crawler import BaseCrawler
from backend.crawlers.config import CrawlTarget, CrawlerConfig
from backend.crawlers.registry import get_all_targets
from backend.crawlers.manifest import CrawlManifest
from backend.crawlers.ms_sos_crawler import MSSoSCrawler
from backend.crawlers.tn_crawler import TNSoSCrawler
from backend.crawlers.generic_crawler import GenericCrawler
from backend.crawlers.specialized.al_admin_crawler import ALAdminCrawler
from backend.crawlers.specialized.la_doa_crawler import LADoACrawler
from backend.crawlers.specialized.ar_sos_crawler import ARSoSCrawler
from backend.crawlers.specialized.ga_sos_crawler import GASoSCrawler
from backend.crawlers.specialized.tx_sos_crawler import TXSoSCrawler


# Crawler type -> class mapping
CRAWLER_CLASSES: dict[str, type[BaseCrawler]] = {
    "ms_sos": MSSoSCrawler,
    "tn_sos": TNSoSCrawler,
    "generic": GenericCrawler,
    "al_admin": ALAdminCrawler,
    "la_doa": LADoACrawler,
    "ar_sos": ARSoSCrawler,
    "ga_sos": GASoSCrawler,
    "tx_sos": TXSoSCrawler,
}


def get_crawler(crawler_type: str, **kwargs) -> BaseCrawler:
    """Instantiate the appropriate crawler class."""
    cls = CRAWLER_CLASSES.get(crawler_type, GenericCrawler)
    return cls(**kwargs)


def run_crawl(
    states: list[str] | None = None,
    agency_types: list[str] | None = None,
    dest_root: str = "./crawled_documents",
    upload_to_s3: bool = False,
) -> dict:
    """
    Run the crawl pipeline for the specified targets.

    Returns a summary dict with crawl_id, totals, and manifest path.
    """
    targets = get_all_targets(states=states, agency_types=agency_types)

    if not targets:
        print("No targets matched the specified filters.")
        return {"crawl_id": "", "total_downloaded": 0, "total_errors": 0}

    print(f"Crawling {len(targets)} targets...")

    # Group targets by crawler_type to reuse sessions
    grouped: dict[str, list[CrawlTarget]] = {}
    for t in targets:
        grouped.setdefault(t.crawler_type, []).append(t)

    all_results = []
    for crawler_type, type_targets in grouped.items():
        crawler = get_crawler(crawler_type, dest_root=dest_root)
        results = crawler.crawl_targets(type_targets)
        all_results.extend(results)

    # Generate manifest
    manifest = CrawlManifest.from_results(all_results)
    manifest_path = Path(dest_root) / "manifest.json"
    manifest.save(manifest_path)
    print(f"\nManifest saved: {manifest_path}")

    # Check for previous manifest and compute diff
    prev_manifest_path = Path(dest_root) / "manifest_previous.json"
    if prev_manifest_path.exists():
        try:
            prev = CrawlManifest.load(prev_manifest_path)
            diff = manifest.diff(prev)
            print(f"\nChanges since last crawl:")
            print(f"  New documents: {len(diff['new'])}")
            print(f"  Removed: {len(diff['removed'])}")
            print(f"  Changed: {len(diff['changed'])}")
            print(f"  Unchanged: {diff['unchanged_count']}")
        except Exception as e:
            print(f"Could not compute diff: {e}")

    # Upload to S3 if requested
    if upload_to_s3:
        _upload_to_s3(dest_root, manifest)

    print(f"\nCrawl complete: {manifest.total_downloaded} downloaded, {manifest.total_errors} errors")

    return {
        "crawl_id": manifest.crawl_id,
        "total_targets": manifest.total_targets,
        "total_discovered": manifest.total_discovered,
        "total_downloaded": manifest.total_downloaded,
        "total_errors": manifest.total_errors,
        "manifest_path": str(manifest_path),
    }


def _upload_to_s3(dest_root: str, manifest: CrawlManifest) -> None:
    """Upload crawled documents to S3."""
    try:
        import boto3
    except ImportError:
        print("boto3 not available — skipping S3 upload")
        return

    s3 = boto3.client("s3")
    bucket = "ms-sos-legal-documents"
    prefix = "crawled-documents"

    for entry in manifest.entries:
        for doc in entry.documents:
            if not doc.saved_path:
                continue
            s3_key = f"{prefix}/{entry.state.lower()}/{entry.agency_type}/{doc.filename}"
            try:
                s3.upload_file(doc.saved_path, bucket, s3_key)
            except Exception as e:
                print(f"  S3 upload failed for {doc.filename}: {e}")

    # Upload manifest
    manifest_s3_key = f"{prefix}/manifests/{manifest.crawl_id}.json"
    try:
        s3.upload_file(
            str(Path(dest_root) / "manifest.json"),
            bucket,
            manifest_s3_key,
        )
        print(f"Manifest uploaded to s3://{bucket}/{manifest_s3_key}")
    except Exception as e:
        print(f"Failed to upload manifest: {e}")


def main():
    parser = argparse.ArgumentParser(
        description="Multi-state regulatory document crawler"
    )
    parser.add_argument(
        "--state", action="append", dest="states",
        help="State codes to crawl (e.g. MS, TN). Repeat for multiple. Default: all.",
    )
    parser.add_argument(
        "--agency", action="append", dest="agency_types",
        help="Agency types to crawl (medical, real_estate, dental). Repeat for multiple. Default: all.",
    )
    parser.add_argument(
        "--dest", default="./crawled_documents",
        help="Destination root directory (default: ./crawled_documents)",
    )
    parser.add_argument(
        "--s3", action="store_true",
        help="Upload results to S3 after crawling",
    )

    args = parser.parse_args()
    run_crawl(
        states=args.states,
        agency_types=args.agency_types,
        dest_root=args.dest,
        upload_to_s3=args.s3,
    )


if __name__ == "__main__":
    main()
