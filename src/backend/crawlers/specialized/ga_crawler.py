"""
Georgia-specific regulatory document crawler.

Georgia state board websites (*.georgia.gov) often use Drupal-based CMS
with documents hosted under /document/ or /media/ paths.
"""

from __future__ import annotations

from backend.crawlers.base_crawler import BaseCrawler, LinkRecord
from backend.crawlers.config import CrawlTarget


class GACrawler(BaseCrawler):
    """
    Crawler for Georgia regulatory boards.

    Georgia boards use georgia.gov infrastructure. Uses the standard
    2-tier crawl with Georgia domain filtering.
    """

    def discover_links(self, target: CrawlTarget) -> tuple[str, list[LinkRecord]]:
        allowed = target.allowed_domains or ("georgia.gov",)
        return self.two_tier_crawl(target.url, allowed_domains=allowed)
