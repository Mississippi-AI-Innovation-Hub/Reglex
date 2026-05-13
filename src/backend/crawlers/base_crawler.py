"""
Abstract base class for state regulatory document crawlers.

Extracted from the 2-tier crawl pattern in tn_documents.py:
  1. Root page scan — fetch a board/agency homepage, extract links
  2. Keyword-matched subpage crawl — follow links matching regulatory keywords,
     then extract document links from those subpages
"""

from __future__ import annotations

import re
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable
from urllib.parse import urljoin, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup

from backend.crawlers.config import CrawlTarget


DEFAULT_BROWSER_UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36"
)

ALLOWED_DOC_EXTENSIONS = {
    ".pdf", ".doc", ".docx", ".xls", ".xlsx",
    ".ppt", ".pptx", ".txt", ".rtf", ".html", ".htm",
}

# Expanded keyword list for Phase 2 use cases
RULES_KEYWORDS = (
    "rule", "rules", "regulation", "regulations",
    "policy", "policies", "statute", "law",
    "chapter", "board minutes", "board meeting",
    "disciplinary",
    # Phase 2 additions
    "fee", "fine", "penalty", "license", "licensure",
    "reciprocity", "examination", "amendment",
    "statutory authority", "renewal", "application",
    "administrative code", "admin code",
)


@dataclass(frozen=True)
class LinkRecord:
    """A discovered document link with provenance."""
    url: str
    text: str
    found_on: str


@dataclass
class CrawlResult:
    """Result of crawling a single target."""
    target: CrawlTarget
    page_title: str = ""
    discovered_links: list[LinkRecord] = field(default_factory=list)
    downloaded_files: list[dict] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def _clean_url(url: str) -> str:
    parsed = urlparse(url)
    parsed = parsed._replace(fragment="")
    return urlunparse(parsed)


def _is_document_url(url: str) -> bool:
    path = urlparse(url).path.lower()
    return any(path.endswith(ext) for ext in ALLOWED_DOC_EXTENSIONS)


def _keyword_match(text_or_url: str) -> bool:
    value = text_or_url.lower()
    return any(kw in value for kw in RULES_KEYWORDS)


def _slugify(text: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return value or "board"


def _title_from_page(html: str, fallback: str = "board") -> str:
    soup = BeautifulSoup(html, "html.parser")
    title_tag = soup.find("title")
    if title_tag and title_tag.get_text(strip=True):
        return title_tag.get_text(" ", strip=True)
    return fallback


class BaseCrawler(ABC):
    """
    Abstract base class for regulatory document crawlers.

    Subclasses must implement ``discover_links`` to define how document links
    are extracted from a particular state's web infrastructure. The base class
    provides the 2-tier crawl-and-download pipeline.
    """

    def __init__(
        self,
        dest_root: str | Path = "./crawled_documents",
        timeout_s: float = 30.0,
        max_subpages: int = 20,
        retries: int = 2,
    ):
        self.dest_root = Path(dest_root)
        self.timeout_s = timeout_s
        self.max_subpages = max_subpages
        self.retries = retries
        self._session: requests.Session | None = None

    @property
    def session(self) -> requests.Session:
        if self._session is None:
            self._session = requests.Session()
            self._session.headers.update({
                "User-Agent": DEFAULT_BROWSER_UA,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
            })
        return self._session

    def fetch(self, url: str) -> str:
        """GET a URL with retry logic. Returns raw HTML text."""
        last_exc: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                resp = self.session.get(url, timeout=self.timeout_s)
                resp.raise_for_status()
                return resp.text
            except requests.RequestException as exc:
                last_exc = exc
                if attempt >= self.retries:
                    raise
                time.sleep(1 + attempt)
        raise last_exc or RuntimeError(f"Failed to fetch {url}")

    # ── Link discovery (the 2-tier pattern) ─────────────────────────────

    @abstractmethod
    def discover_links(self, target: CrawlTarget) -> tuple[str, list[LinkRecord]]:
        """
        Discover document links for a crawl target.

        Returns:
            (page_title, list_of_link_records)
        """

    def _extract_links_from_html(
        self,
        html: str,
        source_url: str,
        *,
        allowed_domains: Iterable[str] | None = None,
        allow_queue_subpages: bool = True,
    ) -> tuple[list[LinkRecord], list[str]]:
        """
        Parse an HTML page and return (document_links, subpage_urls).

        This is the shared extraction logic used by the 2-tier pattern:
        - Direct document links (PDFs, DOCs, etc.) are collected immediately
        - Keyword-matching HTML links on allowed domains are queued for subpage crawl
        """
        doc_links: list[LinkRecord] = []
        subpages: list[str] = []
        seen_urls: set[str] = set()

        soup = BeautifulSoup(html, "html.parser")
        for anchor in soup.select("a[href]"):
            raw_href = (anchor.get("href") or "").strip()
            if not raw_href:
                continue
            full_url = _clean_url(urljoin(source_url, raw_href))
            text = anchor.get_text(" ", strip=True)

            if _is_document_url(full_url):
                if full_url not in seen_urls:
                    seen_urls.add(full_url)
                    doc_links.append(LinkRecord(url=full_url, text=text, found_on=source_url))
                continue

            if not allow_queue_subpages:
                continue

            parsed = urlparse(full_url)
            if allowed_domains:
                if not any(parsed.netloc.endswith(d) for d in allowed_domains):
                    continue
            if parsed.scheme not in {"http", "https"}:
                continue
            if _keyword_match(text) or _keyword_match(full_url):
                if full_url not in seen_urls:
                    seen_urls.add(full_url)
                    subpages.append(full_url)

        return doc_links, subpages

    def two_tier_crawl(
        self,
        page_url: str,
        allowed_domains: Iterable[str] | None = None,
    ) -> tuple[str, list[LinkRecord]]:
        """
        Standard 2-tier crawl: root page -> keyword-matched subpages.

        This is the default implementation used by GenericCrawler and TNCrawler.
        """
        root_html = self.fetch(page_url)
        page_title = _title_from_page(root_html, fallback=page_url)

        all_doc_links: list[LinkRecord] = []
        seen_doc_urls: set[str] = set()

        # Tier 1: extract from root page
        doc_links, subpages = self._extract_links_from_html(
            root_html, page_url,
            allowed_domains=allowed_domains,
            allow_queue_subpages=True,
        )
        for link in doc_links:
            if link.url not in seen_doc_urls:
                seen_doc_urls.add(link.url)
                all_doc_links.append(link)

        # Tier 2: crawl subpages
        visited: set[str] = set()
        for subpage in subpages:
            if len(visited) >= self.max_subpages:
                break
            if subpage in visited:
                continue
            visited.add(subpage)
            try:
                html = self.fetch(subpage)
            except requests.RequestException:
                continue
            sub_links, _ = self._extract_links_from_html(
                html, subpage,
                allowed_domains=allowed_domains,
                allow_queue_subpages=False,
            )
            for link in sub_links:
                if link.url not in seen_doc_urls:
                    seen_doc_urls.add(link.url)
                    all_doc_links.append(link)

        return page_title, all_doc_links

    # ── Download ────────────────────────────────────────────────────────

    def download_file(
        self,
        url: str,
        dest_dir: Path,
        filename: str | None = None,
    ) -> Path:
        """Download a single file to dest_dir. Returns the saved path."""
        dest_dir.mkdir(parents=True, exist_ok=True)
        resp = self.session.get(url, stream=True, timeout=60.0)
        resp.raise_for_status()

        if filename:
            base_name = Path(filename).name
        else:
            base_name = Path(urlparse(url).path).name or "document"

        if not Path(base_name).suffix:
            content_type = (resp.headers.get("content-type") or "").lower()
            if "pdf" in content_type:
                base_name = f"{base_name}.pdf"
            elif "html" in content_type:
                base_name = f"{base_name}.html"
            elif "word" in content_type or "docx" in content_type:
                base_name = f"{base_name}.docx"

        filepath = dest_dir / base_name
        if filepath.exists():
            stem, suffix = filepath.stem, filepath.suffix
            counter = 2
            while filepath.exists():
                filepath = dest_dir / f"{stem}_{counter}{suffix}"
                counter += 1

        with open(filepath, "wb") as out:
            for chunk in resp.iter_content(chunk_size=8192):
                if chunk:
                    out.write(chunk)
        return filepath

    # ── Full crawl pipeline ─────────────────────────────────────────────

    def crawl(self, target: CrawlTarget) -> CrawlResult:
        """
        Full crawl pipeline for a single target:
        1. Discover document links
        2. Download all discovered documents
        3. Return CrawlResult with metadata
        """
        result = CrawlResult(target=target)

        try:
            title, links = self.discover_links(target)
            result.page_title = title
            result.discovered_links = links
        except Exception as exc:
            result.errors.append(f"Discovery failed: {exc}")
            return result

        # Determine destination directory: {state}/{agency_type}/
        dest_dir = (
            self.dest_root
            / target.state.upper()
            / target.agency_type
        )

        for idx, link in enumerate(links, start=1):
            try:
                saved = self.download_file(link.url, dest_dir)
                result.downloaded_files.append({
                    "url": link.url,
                    "text": link.text,
                    "found_on": link.found_on,
                    "saved_path": str(saved),
                })
            except Exception as exc:
                result.errors.append(f"Download failed [{idx}/{len(links)}]: {link.url} ({exc})")

        return result

    def crawl_targets(self, targets: Iterable[CrawlTarget]) -> list[CrawlResult]:
        """Crawl multiple targets sequentially."""
        results = []
        for target in targets:
            print(f"Crawling: {target.state} / {target.agency_type} — {target.url}")
            result = self.crawl(target)
            print(
                f"  Discovered: {len(result.discovered_links)}, "
                f"Downloaded: {len(result.downloaded_files)}, "
                f"Errors: {len(result.errors)}"
            )
            results.append(result)
        return results
