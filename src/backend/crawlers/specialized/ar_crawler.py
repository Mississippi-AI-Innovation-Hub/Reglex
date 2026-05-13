"""
Arkansas-specific regulatory document crawler.

Arkansas state board websites (health.arkansas.gov, *.arkansas.gov)
sometimes host rules on separate domains from the main board site.
"""

from __future__ import annotations

from backend.crawlers.base_crawler import BaseCrawler, LinkRecord
from backend.crawlers.config import CrawlTarget


class ARCrawler(BaseCrawler):
    """
    Crawler for Arkansas regulatory boards.

    Arkansas boards may have rules hosted on both the board site and
    health.arkansas.gov. Uses the standard 2-tier crawl with
    expanded domain filtering.
    """

    def discover_links(self, target: CrawlTarget) -> tuple[str, list[LinkRecord]]:
        allowed = target.allowed_domains or ("arkansas.gov",)
        return self.two_tier_crawl(target.url, allowed_domains=allowed)
