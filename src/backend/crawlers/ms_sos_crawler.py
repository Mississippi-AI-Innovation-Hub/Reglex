"""
Mississippi Secretary of State document crawler.

Refactored from documents.py — preserves the POST-based API pattern
for searching the MS SOS Administrative Code endpoint.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Literal

import requests
from bs4 import BeautifulSoup

from backend.crawlers.base_crawler import BaseCrawler, LinkRecord, CrawlResult
from backend.crawlers.config import CrawlTarget


SEARCH_URL = "https://www.sos.ms.gov/adminsearch/AdminSearchService.asmx/CodeSearch"
WARMUP_URL = "https://www.sos.ms.gov/adminsearch/default.aspx"
BASE_DOWNLOAD = "https://www.sos.ms.gov/adminsearch/ACCode/"


class MSSoSCrawler(BaseCrawler):
    """
    Crawler for Mississippi SOS Administrative Code.

    Uses the POST-based CodeSearch API endpoint to retrieve document listings,
    then downloads PDFs from the ACCode directory.
    """

    def discover_links(self, target: CrawlTarget) -> tuple[str, list[LinkRecord]]:
        """
        Discover documents via the MS SOS CodeSearch API.

        The MS SOS uses a SOAP-like JSON POST endpoint instead of standard HTML pages.
        Each agency has a numeric ID used in the POST payload.
        """
        agency_id = target.extra.get("agency_id", "")
        if not agency_id:
            raise ValueError(f"MSSoSCrawler requires 'agency_id' in target.extra for {target.agency_name}")

        # Warmup GET (the SOS site sometimes needs a session cookie)
        try:
            self.session.get(WARMUP_URL, timeout=self.timeout_s)
        except requests.RequestException:
            pass

        # Update session headers for the API call
        self.session.headers.update({
            "Origin": "https://www.sos.ms.gov",
            "Referer": WARMUP_URL,
            "X-Requested-With": "XMLHttpRequest",
            "Content-Type": "application/json; charset=UTF-8",
        })

        payload = {
            "tmpSubject": "",
            "tmpAgency": str(agency_id),
            "tmpPartRange1": "",
            "tmpPartRange2": "",
            "tmpRuleSum": "",
            "tmpOrder": "PartNo",
            "tmpOrderDirec": "Ascending",
            "tmpSearchDate1": "",
            "tmpSearchDate2": "",
            "tmpDateType": "0",
        }

        last_exc: Exception | None = None
        resp_text = ""
        for attempt in range(self.retries + 1):
            try:
                resp = self.session.post(SEARCH_URL, json=payload, timeout=self.timeout_s)
                resp.raise_for_status()
                resp_text = resp.text
                break
            except requests.RequestException as exc:
                last_exc = exc
                if attempt >= self.retries:
                    raise
                time.sleep(1 + attempt)

        count, filenames = self._parse_code_search_result(resp_text)

        links = []
        for fname in filenames:
            doc_url = BASE_DOWNLOAD + fname
            links.append(LinkRecord(
                url=doc_url,
                text=fname,
                found_on=SEARCH_URL,
            ))

        return target.agency_name, links

    @staticmethod
    def _parse_code_search_result(resp: str | dict) -> tuple[int, list[str]]:
        """
        Parse a CodeSearch response and return (count, list_of_filenames).

        The service returns JSON like {"d":"rec1^rec2^...|15"} where each record
        is tilde-delimited (~). The filename (PDF) is the last ~-delimited field.
        """
        if isinstance(resp, dict):
            val = resp.get("d") or resp.get("D") or ""
            if not isinstance(val, str):
                val = str(val)
        else:
            if isinstance(resp, str):
                s = resp.strip()
                if s.startswith("{") or '"d"' in s or '"D"' in s:
                    try:
                        parsed = json.loads(s)
                        if isinstance(parsed, dict):
                            val = parsed.get("d") or parsed.get("D") or ""
                            if not isinstance(val, str):
                                val = str(val)
                        else:
                            val = s
                    except Exception:
                        val = s
                else:
                    val = s
            else:
                val = str(resp)

        val = val.strip()
        total_count: int | None = None
        if "|" in val:
            parts = val.rsplit("|", 1)
            if len(parts) == 2 and parts[1].strip().isdigit():
                total_count = int(parts[1].strip())
                val = parts[0]

        records = [r for r in val.split("^") if r.strip()]
        filenames: list[str] = []
        for rec in records:
            if "~" in rec:
                candidate = rec.rsplit("~", 1)[-1].strip()
            else:
                candidate = rec.strip()
            candidate = candidate.strip(' "\'{}[]')
            if "|" in candidate:
                candidate = candidate.split("|", 1)[0].strip()
            if candidate:
                filenames.append(candidate)

        if total_count is not None:
            return total_count, filenames
        return len(filenames), filenames
