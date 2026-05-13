"""
Louisiana Division of Administration / Office of State Register crawler.

Downloads administrative code volumes as DOCX files from the DOA website.

Source: https://www.doa.la.gov/doa/osr/louisiana-administrative-code/
"""

from __future__ import annotations

import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from backend.crawlers.base_crawler import BaseCrawler, LinkRecord
from backend.crawlers.config import CrawlTarget


INDEX_URL = "https://www.doa.la.gov/doa/osr/louisiana-administrative-code/"


class LADoACrawler(BaseCrawler):
    """
    Crawler for the Louisiana Administrative Code.

    Scrapes the DOA index page for DOCX download links matching the
    target's volume file identifier (e.g. '46v45' for Title 46, Part XLV).
    """

    def discover_links(self, target: CrawlTarget) -> tuple[str, list[LinkRecord]]:
        volume_file = target.extra.get("volume_file", "")
        if not volume_file:
            raise ValueError(
                f"LADoACrawler requires 'volume_file' in target.extra for {target.agency_name}"
            )

        html = self.fetch(INDEX_URL)
        soup = BeautifulSoup(html, "html.parser")

        links: list[LinkRecord] = []

        for anchor in soup.select("a[href]"):
            href = (anchor.get("href") or "").strip()
            if not href:
                continue
            # Match the volume file pattern in the URL
            if volume_file.lower() in href.lower() and href.lower().endswith(".docx"):
                full_url = urljoin(INDEX_URL, href)
                text = anchor.get_text(" ", strip=True) or f"Title {target.extra.get('title', '')} Part {target.extra.get('part', '')}"
                links.append(LinkRecord(url=full_url, text=text, found_on=INDEX_URL))

        # If we didn't find the specific file by name, try a broader search
        # for any docx in the page that matches the volume number
        if not links:
            vol_pattern = re.compile(re.escape(volume_file), re.IGNORECASE)
            for anchor in soup.select("a[href]"):
                href = (anchor.get("href") or "").strip()
                if href and (".docx" in href.lower() or ".doc" in href.lower()):
                    if vol_pattern.search(href):
                        full_url = urljoin(INDEX_URL, href)
                        text = anchor.get_text(" ", strip=True) or volume_file
                        links.append(LinkRecord(url=full_url, text=text, found_on=INDEX_URL))

        return target.agency_name, links
