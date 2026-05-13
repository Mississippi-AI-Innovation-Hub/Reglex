"""
Tennessee SoS Division of Publications crawler.

Crawls the official TN administrative rules from the SoS publications site.
Each board has an HTML index page listing chapter PDFs as direct download links.

Source: https://publications.tnsosfiles.com/rules/{CODE}/{CODE}.htm
"""

from __future__ import annotations

import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from backend.crawlers.base_crawler import BaseCrawler, LinkRecord
from backend.crawlers.config import CrawlTarget


class TNSoSCrawler(BaseCrawler):
    """
    Crawler for Tennessee SoS administrative rules.

    Fetches the board index page (e.g. /rules/0880/0880.htm) and extracts
    all PDF download links. PDFs are served from S3 via CloudFront.
    """

    def discover_links(self, target: CrawlTarget) -> tuple[str, list[LinkRecord]]:
        code = target.extra.get("code", "")
        index_url = target.url

        html = self.fetch(index_url)
        soup = BeautifulSoup(html, "html.parser")

        page_title = target.agency_name
        title_tag = soup.find("title")
        if title_tag and title_tag.get_text(strip=True):
            page_title = title_tag.get_text(" ", strip=True)

        links: list[LinkRecord] = []
        seen: set[str] = set()

        for anchor in soup.select("a[href]"):
            href = (anchor.get("href") or "").strip()
            if not href:
                continue
            full_url = urljoin(index_url, href)
            if full_url.lower().endswith(".pdf") and full_url not in seen:
                seen.add(full_url)
                text = anchor.get_text(" ", strip=True) or href.split("/")[-1]
                links.append(LinkRecord(url=full_url, text=text, found_on=index_url))

        return page_title, links
