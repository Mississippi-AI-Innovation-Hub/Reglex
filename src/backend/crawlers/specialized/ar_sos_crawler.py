"""
Arkansas Secretary of State Rules & Regulations crawler.

Searches the SoS rules filing system via POST with CSRF token,
then downloads PDFs (served via S3 presigned URLs).

Source: https://sos-rules-reg.ark.org/rules/search
"""

from __future__ import annotations

import re
import time
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from backend.crawlers.base_crawler import BaseCrawler, LinkRecord
from backend.crawlers.config import CrawlTarget


class ARSoSCrawler(BaseCrawler):
    """
    Crawler for the Arkansas SoS Rules & Regulations system.

    1. GET the search page to obtain the CSRF token and session cookie
    2. POST with agency_id to get search results
    3. Extract PDF links from the results table
    """

    def discover_links(self, target: CrawlTarget) -> tuple[str, list[LinkRecord]]:
        search_url = target.extra.get("search_url", "https://sos-rules-reg.ark.org/rules/search")
        agency_id = target.extra.get("agency_id", "")
        alt_agency_id = target.extra.get("alt_agency_id", "")

        if not agency_id:
            raise ValueError(
                f"ARSoSCrawler requires 'agency_id' in target.extra for {target.agency_name}"
            )

        all_links: list[LinkRecord] = []
        seen: set[str] = set()

        # Search both agency IDs if available
        agency_ids = [agency_id]
        if alt_agency_id:
            agency_ids.append(alt_agency_id)

        for aid in agency_ids:
            links = self._search_agency(search_url, aid, target.agency_name)
            for link in links:
                if link.url not in seen:
                    seen.add(link.url)
                    all_links.append(link)

        return target.agency_name, all_links

    def _search_agency(
        self, search_url: str, agency_id: str, agency_name: str
    ) -> list[LinkRecord]:
        """Search for rules for a specific agency ID."""
        # Step 1: GET the search page for CSRF token
        try:
            page_html = self.fetch(search_url)
        except requests.RequestException as exc:
            return []

        soup = BeautifulSoup(page_html, "html.parser")
        token_input = soup.find("input", {"name": "_token"})
        csrf_token = token_input["value"] if token_input else ""

        if not csrf_token:
            # Try meta tag
            meta = soup.find("meta", {"name": "csrf-token"})
            csrf_token = meta["content"] if meta else ""

        # Step 2: POST search
        payload = {
            "_token": csrf_token,
            "agency_id": agency_id,
            "keywords": "",
            "use_dates": "0",
            "effective_date_start": "",
            "effective_date_end": "",
        }

        try:
            resp = self.session.post(
                search_url,
                data=payload,
                timeout=self.timeout_s,
                headers={"Referer": search_url},
            )
            resp.raise_for_status()
        except requests.RequestException:
            return []

        # Step 3: Extract PDF links from results
        results_soup = BeautifulSoup(resp.text, "html.parser")
        links: list[LinkRecord] = []

        for anchor in results_soup.select("a[href]"):
            href = (anchor.get("href") or "").strip()
            if not href:
                continue
            full_url = urljoin(search_url, href)
            if ".pdf" in full_url.lower() or "/rules/pdf/" in full_url.lower():
                text = anchor.get_text(" ", strip=True) or href.split("/")[-1]
                links.append(LinkRecord(url=full_url, text=text, found_on=search_url))

        return links
