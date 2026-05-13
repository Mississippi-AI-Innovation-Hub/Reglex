"""
Alabama Administrative Code crawler.

Crawls official administrative rules from the Alabama Legislative Services Agency.
Uses the REST PDF endpoint to download chapter-level PDFs.

Source: https://admincode.legislature.state.al.us/api/chapter/{chapterIdText}
"""

from __future__ import annotations

import time

import requests

from backend.crawlers.base_crawler import BaseCrawler, LinkRecord
from backend.crawlers.config import CrawlTarget


BASE_URL = "https://admincode.legislature.state.al.us"
CHAPTER_PDF_URL = f"{BASE_URL}/api/chapter"


class ALAdminCrawler(BaseCrawler):
    """
    Crawler for the Alabama Administrative Code.

    Downloads chapter-level PDFs via the REST API endpoint.
    Each chapter ID follows the pattern: {agency}-X-{number}
    """

    def discover_links(self, target: CrawlTarget) -> tuple[str, list[LinkRecord]]:
        chapters = target.extra.get("chapters", [])
        agency_number = target.extra.get("agency_number", "")

        if not chapters:
            raise ValueError(
                f"ALAdminCrawler requires 'chapters' in target.extra for {target.agency_name}"
            )

        links: list[LinkRecord] = []

        for chapter_id in chapters:
            pdf_url = f"{CHAPTER_PDF_URL}/{chapter_id}"

            # Verify the chapter exists before adding
            try:
                resp = self.session.head(pdf_url, timeout=self.timeout_s, allow_redirects=True)
                if resp.status_code == 200:
                    links.append(LinkRecord(
                        url=pdf_url,
                        text=f"Chapter {chapter_id}",
                        found_on=f"{BASE_URL}/administrative-code/{agency_number}",
                    ))
                time.sleep(0.3)  # Be polite
            except requests.RequestException:
                continue

        return target.agency_name, links
