"""
Crawl manifest generation and diff detection.

Each crawl run produces a manifest.json for tracking document inventory
and detecting changes (new, removed, or modified documents) between runs.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from dataclasses import dataclass, field, asdict

from backend.crawlers.base_crawler import CrawlResult


@dataclass
class DocumentEntry:
    """A single document in the manifest."""
    url: str
    filename: str
    saved_path: str
    file_hash: str
    size_bytes: int
    crawled_at: str


@dataclass
class ManifestEntry:
    """Manifest entry for one crawl target."""
    state: str
    agency_type: str
    agency_name: str
    page_title: str
    source_url: str
    discovered_count: int
    downloaded_count: int
    error_count: int
    documents: list[DocumentEntry] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


@dataclass
class CrawlManifest:
    """Full crawl manifest tracking all targets."""
    crawl_id: str
    started_at: str
    completed_at: str = ""
    total_targets: int = 0
    total_discovered: int = 0
    total_downloaded: int = 0
    total_errors: int = 0
    entries: list[ManifestEntry] = field(default_factory=list)

    @staticmethod
    def _file_hash(filepath: str) -> str:
        """Compute SHA-256 hash of a file."""
        h = hashlib.sha256()
        try:
            with open(filepath, "rb") as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    h.update(chunk)
            return h.hexdigest()
        except (OSError, FileNotFoundError):
            return ""

    @classmethod
    def from_results(cls, results: list[CrawlResult], crawl_id: str | None = None) -> CrawlManifest:
        """Build a manifest from a list of CrawlResults."""
        now = datetime.now(timezone.utc).isoformat()
        manifest = cls(
            crawl_id=crawl_id or hashlib.sha256(now.encode()).hexdigest()[:12],
            started_at=now,
            total_targets=len(results),
        )

        for result in results:
            docs = []
            for dl in result.downloaded_files:
                saved = dl.get("saved_path", "")
                try:
                    size = Path(saved).stat().st_size if saved else 0
                except OSError:
                    size = 0

                docs.append(DocumentEntry(
                    url=dl.get("url", ""),
                    filename=Path(saved).name if saved else "",
                    saved_path=saved,
                    file_hash=cls._file_hash(saved) if saved else "",
                    size_bytes=size,
                    crawled_at=now,
                ))

            entry = ManifestEntry(
                state=result.target.state,
                agency_type=result.target.agency_type,
                agency_name=result.target.agency_name,
                page_title=result.page_title,
                source_url=result.target.url,
                discovered_count=len(result.discovered_links),
                downloaded_count=len(result.downloaded_files),
                error_count=len(result.errors),
                documents=docs,
                errors=result.errors,
            )
            manifest.entries.append(entry)
            manifest.total_discovered += entry.discovered_count
            manifest.total_downloaded += entry.downloaded_count
            manifest.total_errors += entry.error_count

        manifest.completed_at = datetime.now(timezone.utc).isoformat()
        return manifest

    def save(self, path: str | Path) -> Path:
        """Save manifest to JSON file."""
        filepath = Path(path)
        filepath.parent.mkdir(parents=True, exist_ok=True)
        filepath.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")
        return filepath

    @classmethod
    def load(cls, path: str | Path) -> CrawlManifest:
        """Load manifest from JSON file."""
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        entries = []
        for e in data.get("entries", []):
            docs = [DocumentEntry(**d) for d in e.pop("documents", [])]
            entries.append(ManifestEntry(**e, documents=docs))
        data["entries"] = entries
        return cls(**data)

    def diff(self, previous: CrawlManifest) -> dict:
        """
        Compare this manifest against a previous one.
        Returns dict of new, removed, and changed documents.
        """
        prev_docs: dict[str, DocumentEntry] = {}
        for entry in previous.entries:
            for doc in entry.documents:
                prev_docs[doc.url] = doc

        curr_docs: dict[str, DocumentEntry] = {}
        for entry in self.entries:
            for doc in entry.documents:
                curr_docs[doc.url] = doc

        new_urls = set(curr_docs.keys()) - set(prev_docs.keys())
        removed_urls = set(prev_docs.keys()) - set(curr_docs.keys())
        common_urls = set(curr_docs.keys()) & set(prev_docs.keys())

        changed = []
        for url in common_urls:
            if curr_docs[url].file_hash != prev_docs[url].file_hash:
                changed.append(url)

        return {
            "new": [curr_docs[u].filename for u in new_urls],
            "removed": [prev_docs[u].filename for u in removed_urls],
            "changed": [curr_docs[u].filename for u in changed],
            "unchanged_count": len(common_urls) - len(changed),
        }
