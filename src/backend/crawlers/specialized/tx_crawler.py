"""
Texas-specific regulatory document crawler.

Texas state board websites (tmb.state.tx.us, trec.texas.gov, tsbde.texas.gov)
often have rules/regulations organized under specific paths.
"""

from __future__ import annotations

from backend.crawlers.base_crawler import BaseCrawler, LinkRecord
from backend.crawlers.config import CrawlTarget


class TXCrawler(BaseCrawler):
    """
    Crawler for Texas regulatory boards.

    Texas boards typically organize rules under /rules/ or /laws-and-rules/ paths.
    Uses the standard 2-tier crawl with Texas domain filtering.
    """

    def discover_links(self, target: CrawlTarget) -> tuple[str, list[LinkRecord]]:
        allowed = target.allowed_domains or ("texas.gov", "state.tx.us")
        return self.two_tier_crawl(target.url, allowed_domains=allowed)
