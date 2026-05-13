"""
Georgia Secretary of State Administrative Rules crawler.

Crawls the official GA Rules and Regulations from the SoS
Administrative Procedure Division website.

Source: https://rules.sos.ga.gov/
"""

from __future__ import annotations

import re
from urllib.parse import urljoin, quote

from bs4 import BeautifulSoup

from backend.crawlers.base_crawler import BaseCrawler, LinkRecord
from backend.crawlers.config import CrawlTarget


BASE_URL = "https://rules.sos.ga.gov"


class GASoSCrawler(BaseCrawler):
    """
    Crawler for the Georgia SoS Rules and Regulations.

    Fetches the department page (e.g. /gac/360) to list all chapters,
    then collects chapter/rule links. Also grabs the department-level PDF.
    """

    def discover_links(self, target: CrawlTarget) -> tuple[str, list[LinkRecord]]:
        dept = target.extra.get("dept", "")
        if not dept:
            raise ValueError(
                f"GASoSCrawler requires 'dept' in target.extra for {target.agency_name}"
            )

        dept_url = f"{BASE_URL}/gac/{dept}"
        html = self.fetch(dept_url)
        soup = BeautifulSoup(html, "html.parser")

        page_title = target.agency_name
        title_tag = soup.find("title")
        if title_tag and title_tag.get_text(strip=True):
            page_title = title_tag.get_text(" ", strip=True)

        links: list[LinkRecord] = []
        seen: set[str] = set()

        # Collect chapter links — each chapter page contains the rule text
        for anchor in soup.select("a[href]"):
            href = (anchor.get("href") or "").strip()
            if not href:
                continue
            full_url = urljoin(dept_url, href)

            # Direct PDF/doc links
            if any(full_url.lower().endswith(ext) for ext in (".pdf", ".doc", ".docx")):
                if full_url not in seen:
                    seen.add(full_url)
                    text = anchor.get_text(" ", strip=True) or href.split("/")[-1]
                    links.append(LinkRecord(url=full_url, text=text, found_on=dept_url))
                continue

            # Chapter pages under this department (e.g. /gac/360-1)
            if f"/gac/{dept}-" in full_url and full_url not in seen:
                seen.add(full_url)
                text = anchor.get_text(" ", strip=True) or f"Chapter {href.split('/')[-1]}"
                links.append(LinkRecord(url=full_url, text=text, found_on=dept_url))

        # Also look for the department PDF download link
        for anchor in soup.select("a[href*='Download_pdf']"):
            href = (anchor.get("href") or "").strip()
            if href:
                full_url = urljoin(dept_url, href)
                if full_url not in seen:
                    seen.add(full_url)
                    links.append(LinkRecord(
                        url=full_url,
                        text=f"Department {dept} Full PDF",
                        found_on=dept_url,
                    ))

        # If no PDF download link found, construct one
        dept_pdf_found = any("Download_pdf" in l.url for l in links)
        if not dept_pdf_found:
            # Try the known PDF URL pattern
            encoded_name = quote(page_title.upper())
            pdf_url = (
                f"{BASE_URL}/Download_pdf.aspx?st=GASOS&year=2025"
                f"&dept=Departments&pdf=Department+{dept}+{encoded_name}"
            )
            links.append(LinkRecord(
                url=pdf_url,
                text=f"Department {dept} Full PDF",
                found_on=dept_url,
            ))

        return page_title, links
