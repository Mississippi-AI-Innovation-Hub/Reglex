from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from urllib.parse import urljoin, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup


TARGET_PAGES = [
	"https://www.tn.gov/health/health-program-areas/health-professional-boards/dentistry-board.html",
	"https://www.tn.gov/commerce/regboards/trec.html",
	"https://www.tn.gov/health/health-program-areas/health-professional-boards/me-board.html",
]

DEFAULT_BROWSER_UA = (
	"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
	"(KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36"
)

ALLOWED_DOC_EXTENSIONS = {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".txt", ".rtf"}

RULES_KEYWORDS = (
	"rule",
	"rules",
	"regulation",
	"regulations",
	"policy",
	"policies",
	"statute",
	"law",
	"chapter",
	"board minutes",
	"board meeting",
	"disciplinary",
)


@dataclass(frozen=True)
class LinkRecord:
	url: str
	text: str
	found_on: str


def _clean_url(url: str) -> str:
	parsed = urlparse(url)
	parsed = parsed._replace(fragment="")
	return urlunparse(parsed)


def _is_document_url(url: str) -> bool:
	path = urlparse(url).path.lower()
	return any(path.endswith(ext) for ext in ALLOWED_DOC_EXTENSIONS)


def _keyword_match(text_or_url: str) -> bool:
	value = text_or_url.lower()
	return any(keyword in value for keyword in RULES_KEYWORDS)


def _slugify(text: str) -> str:
	value = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
	return value or "board"


def _title_from_page(html: str, fallback: str = "board") -> str:
	soup = BeautifulSoup(html, "html.parser")
	title_tag = soup.find("title")
	if title_tag and title_tag.get_text(strip=True):
		return title_tag.get_text(" ", strip=True)
	return fallback


def _fetch(url: str, session: requests.Session, timeout_s: float, retries: int = 2) -> str:
	last_exc: Exception | None = None
	for attempt in range(retries + 1):
		try:
			resp = session.get(url, timeout=timeout_s)
			resp.raise_for_status()
			return resp.text
		except requests.RequestException as exc:
			last_exc = exc
			if attempt >= retries:
				raise
			time.sleep(1 + attempt)
	raise last_exc or RuntimeError(f"Failed to fetch {url}")


def extract_document_links(
	page_url: str,
	*,
	session: requests.Session | None = None,
	timeout_s: float = 30.0,
	max_subpages: int = 20,
) -> tuple[str, list[LinkRecord]]:
	"""Extract likely rules/regulations document links from a TN board page.

	This performs:
	1) Direct link extraction from the page
	2) One-hop crawl into likely rules/regulation subpages on tn.gov
	"""
	client = session or requests.Session()
	client.headers.update(
		{
			"User-Agent": DEFAULT_BROWSER_UA,
			"Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
			"Accept-Language": "en-US,en;q=0.9",
		}
	)

	root_html = _fetch(page_url, session=client, timeout_s=timeout_s)
	page_title = _title_from_page(root_html, fallback=page_url)

	seen_doc_urls: set[str] = set()
	results: list[LinkRecord] = []
	subpages_to_visit: list[str] = []

	def consume_links(html: str, source_url: str, allow_queue_subpages: bool) -> None:
		soup = BeautifulSoup(html, "html.parser")
		for anchor in soup.select("a[href]"):
			raw_href = (anchor.get("href") or "").strip()
			if not raw_href:
				continue
			full_url = _clean_url(urljoin(source_url, raw_href))
			text = anchor.get_text(" ", strip=True)
			if _is_document_url(full_url):
				if full_url not in seen_doc_urls:
					seen_doc_urls.add(full_url)
					results.append(LinkRecord(url=full_url, text=text, found_on=source_url))
				continue

			if not allow_queue_subpages:
				continue

			parsed = urlparse(full_url)
			if not parsed.netloc.endswith("tn.gov"):
				continue
			if parsed.scheme not in {"http", "https"}:
				continue

			if _keyword_match(text) or _keyword_match(full_url):
				subpages_to_visit.append(full_url)

	consume_links(root_html, source_url=page_url, allow_queue_subpages=True)

	visited_subpages: set[str] = set()
	for subpage in subpages_to_visit:
		if len(visited_subpages) >= max_subpages:
			break
		if subpage in visited_subpages:
			continue
		visited_subpages.add(subpage)
		try:
			html = _fetch(subpage, session=client, timeout_s=timeout_s, retries=1)
		except requests.RequestException:
			continue
		consume_links(html, source_url=subpage, allow_queue_subpages=False)

	return page_title, results


def _filename_from_url(url: str) -> str:
	name = Path(urlparse(url).path).name
	return name or "document"


def download_document(
	url: str,
	*,
	dest_dir: str | Path,
	session: requests.Session | None = None,
	timeout_s: float = 60.0,
	filename: str | None = None,
) -> Path:
	dirpath = Path(dest_dir)
	dirpath.mkdir(parents=True, exist_ok=True)

	client = session or requests.Session()
	resp = client.get(url, stream=True, timeout=timeout_s)
	resp.raise_for_status()

	base_name = Path(filename).name if filename else _filename_from_url(url)
	if not Path(base_name).suffix:
		content_type = (resp.headers.get("content-type") or "").lower()
		if "pdf" in content_type:
			base_name = f"{base_name}.pdf"

	if not base_name:
		raise ValueError(f"Could not infer filename for URL: {url}")

	filepath = dirpath / base_name
	if filepath.exists():
		stem, suffix = filepath.stem, filepath.suffix
		counter = 2
		while filepath.exists():
			filepath = dirpath / f"{stem}_{counter}{suffix}"
			counter += 1

	with open(filepath, "wb") as out:
		for chunk in resp.iter_content(chunk_size=8192):
			if chunk:
				out.write(chunk)

	return filepath


def scrape_tn_boards(
	urls: Iterable[str] = TARGET_PAGES,
	*,
	dest_root: str | Path = "./tn_documents",
	timeout_s: float = 30.0,
) -> dict:
	url_list = list(urls)
	root = Path(dest_root)
	root.mkdir(parents=True, exist_ok=True)

	client = requests.Session()
	client.headers.update({"User-Agent": DEFAULT_BROWSER_UA})

	summary: dict[str, dict] = {}
	total_discovered = 0
	total_downloaded = 0

	for page_url in url_list:
		print(f"Scanning: {page_url}")
		try:
			title, links = extract_document_links(page_url, session=client, timeout_s=timeout_s)
		except Exception as exc:
			print(f"  Failed to scan page: {exc}")
			summary[page_url] = {"title": page_url, "error": str(exc), "documents": []}
			continue

		folder_name = _slugify(title)
		board_dir = root / folder_name
		board_dir.mkdir(parents=True, exist_ok=True)

		print(f"  Found {len(links)} candidate documents")
		downloaded_records = []
		for idx, rec in enumerate(links, start=1):
			try:
				saved = download_document(rec.url, dest_dir=board_dir, session=client)
			except Exception as exc:
				print(f"    [{idx}/{len(links)}] Failed: {rec.url} ({exc})")
				continue

			total_downloaded += 1
			downloaded_records.append(
				{
					"url": rec.url,
					"text": rec.text,
					"found_on": rec.found_on,
					"saved_path": str(saved),
				}
			)
			print(f"    [{idx}/{len(links)}] Saved: {saved.name}")

		total_discovered += len(links)
		summary[page_url] = {
			"title": title,
			"discovered_count": len(links),
			"downloaded_count": len(downloaded_records),
			"documents": downloaded_records,
		}

	manifest = {
		"total_pages": len(url_list),
		"total_discovered": total_discovered,
		"total_downloaded": total_downloaded,
		"pages": summary,
	}

	manifest_path = root / "manifest.json"
	manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
	print(f"Wrote manifest: {manifest_path}")
	print(f"Done. Discovered={total_discovered}, Downloaded={total_downloaded}")
	return manifest


if __name__ == "__main__":
	scrape_tn_boards()
