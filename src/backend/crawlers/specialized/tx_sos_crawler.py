"""
Texas Administrative Code crawler using Playwright headless WebKit.

The TX SoS migrated their TAC to an Appian SPA (JS-rendered) that
cannot be scraped with HTTP requests. This crawler uses Playwright
with Apple's WebKit engine to navigate the site headlessly.

Source: https://texas-sos.appianportalsgov.com/rules-and-meetings

Flow:
  1. Load Part page → extract chapter numbers from rendered text
  2. Load each Chapter page → extract rule recordIds from page source
  3. Load each rule via VIEW_TAC_SUMMARY → extract text from iframes
  4. Save as HTML files
"""

from __future__ import annotations

import re
import time
from pathlib import Path

from backend.crawlers.base_crawler import BaseCrawler, LinkRecord, CrawlResult
from backend.crawlers.config import CrawlTarget

PORTAL_BASE = "https://texas-sos.appianportalsgov.com/rules-and-meetings"


class TXSoSCrawler(BaseCrawler):
    """
    Headless WebKit crawler for the Texas SoS Administrative Code.

    Uses Playwright to render the Appian SPA and extract rule text
    from dynamically-loaded iframes.
    """

    def discover_links(self, target: CrawlTarget) -> tuple[str, list[LinkRecord]]:
        """Discover all rule recordIds for this Part."""
        title_num = target.extra.get("title", "22")
        part_num = target.extra.get("part", "")

        if not part_num:
            raise ValueError(
                f"TXSoSCrawler requires 'part' in target.extra for {target.agency_name}"
            )

        from playwright.sync_api import sync_playwright

        links: list[LinkRecord] = []

        with sync_playwright() as p:
            browser = p.webkit.launch(headless=True)
            page = browser.new_page()

            # Step 1: Load Part page to get chapter list
            part_url = f"{PORTAL_BASE}?interface=VIEW_TAC&title={title_num}&part={part_num}"
            page.goto(part_url, wait_until="networkidle", timeout=60000)
            time.sleep(3)

            # Extract chapter numbers from visible text
            body_text = page.inner_text("body")
            chapters = re.findall(r'CHAPTER\s+(\d+)', body_text)
            # Deduplicate while preserving order
            seen_ch = set()
            unique_chapters = []
            for ch in chapters:
                if ch not in seen_ch:
                    seen_ch.add(ch)
                    unique_chapters.append(ch)
            chapters = unique_chapters

            print(f"  Found {len(chapters)} chapters for Part {part_num}")

            # Step 2: For each chapter, get rule recordIds
            for ch_num in chapters:
                ch_url = (
                    f"{PORTAL_BASE}?chapter={ch_num}&interface=VIEW_TAC"
                    f"&part={part_num}&title={title_num}"
                )
                try:
                    page.goto(ch_url, wait_until="networkidle", timeout=60000)
                    time.sleep(2)
                except Exception:
                    continue

                # Extract recordIds from page source HTML
                html = page.content()
                record_ids = re.findall(r'recordId[=:](\d+)', html)

                # Extract rule labels from visible text
                ch_text = page.inner_text("body")
                labels = re.findall(r'(§[\d.]+)', ch_text)

                # Deduplicate recordIds, pair with labels
                seen_rid = set()
                ch_rules = []
                for rid in record_ids:
                    if rid not in seen_rid:
                        seen_rid.add(rid)
                        ch_rules.append(rid)

                for i, rid in enumerate(ch_rules):
                    label = labels[i] if i < len(labels) else f"Ch{ch_num}_Rule{i+1}"
                    rule_url = f"{PORTAL_BASE}?interface=VIEW_TAC_SUMMARY&recordId={rid}"
                    links.append(LinkRecord(
                        url=rule_url,
                        text=label,
                        found_on=ch_url,
                    ))

                print(f"    Chapter {ch_num}: {len(ch_rules)} rules")

            print(f"  Total rules found: {len(links)}")
            browser.close()

        return target.agency_name, links

    def crawl(self, target: CrawlTarget) -> CrawlResult:
        """
        Override crawl to use Playwright for downloading rule text.

        Instead of HTTP downloads, we render each rule page and extract
        the text from iframes.
        """
        result = CrawlResult(target=target)

        try:
            title, links = self.discover_links(target)
            result.page_title = title
            result.discovered_links = links
        except Exception as exc:
            result.errors.append(f"Discovery failed: {exc}")
            return result

        if not links:
            return result

        dest_dir = self.dest_root / target.state.upper() / target.agency_type
        dest_dir.mkdir(parents=True, exist_ok=True)

        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.webkit.launch(headless=True)
            page = browser.new_page()

            for idx, link in enumerate(links, start=1):
                try:
                    html_content = self._fetch_rule_text(page, link.url, link.text)
                    if html_content:
                        safe_name = re.sub(r'[^a-zA-Z0-9_.§\-]+', '_', link.text).strip('_')
                        if not safe_name:
                            safe_name = f"rule_{idx}"
                        filename = f"{safe_name}.html"
                        filepath = dest_dir / filename

                        if filepath.exists():
                            stem, suffix = filepath.stem, filepath.suffix
                            counter = 2
                            while filepath.exists():
                                filepath = dest_dir / f"{stem}_{counter}{suffix}"
                                counter += 1

                        filepath.write_text(html_content, encoding="utf-8")
                        result.downloaded_files.append({
                            "url": link.url,
                            "text": link.text,
                            "found_on": link.found_on,
                            "saved_path": str(filepath),
                        })
                    else:
                        result.errors.append(f"No content [{idx}/{len(links)}]: {link.text}")

                    if idx % 20 == 0:
                        print(f"    Progress: {idx}/{len(links)} rules")

                except Exception as exc:
                    result.errors.append(f"Failed [{idx}/{len(links)}]: {link.text} ({exc})")

            browser.close()

        return result

    @staticmethod
    def _fetch_rule_text(page, rule_url: str, label: str) -> str:
        """
        Load a rule's VIEW_TAC_SUMMARY page and extract full text
        from the main page and dynamic iframes.
        """
        try:
            page.goto(rule_url, wait_until="networkidle", timeout=30000)
            time.sleep(2)
        except Exception:
            return ""

        parts = []

        # Main frame: metadata (title, part, chapter, rule name)
        main_text = page.inner_text("body").strip()
        if main_text:
            parts.append(main_text)

        # Iframes: rule body text and source note
        for frame in page.frames:
            if frame == page.main_frame:
                continue
            try:
                frame_text = frame.locator("body").inner_text(timeout=5000)
                if frame_text and len(frame_text.strip()) > 10:
                    parts.append(frame_text.strip())
            except Exception:
                continue

        if not parts:
            return ""

        # Build clean HTML with proper paragraph wrapping
        html = (
            f"<!DOCTYPE html>\n<html lang='en'>\n"
            f"<head><meta charset='utf-8'><title>{label} - Texas Administrative Code</title></head>\n"
            f"<body>\n"
        )
        for part in parts:
            # Split into paragraphs on blank lines, wrap each in <p>
            lines = part.split("\n")
            current = []
            for line in lines:
                stripped = line.strip()
                if not stripped:
                    if current:
                        text = " ".join(current)
                        escaped = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                        html += f"<p>{escaped}</p>\n"
                        current = []
                else:
                    current.append(stripped)
            if current:
                text = " ".join(current)
                escaped = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                html += f"<p>{escaped}</p>\n"
            html += "<hr>\n"
        html += "</body>\n</html>"

        return html
