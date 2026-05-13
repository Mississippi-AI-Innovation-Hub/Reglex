"""
Generic HTML crawler for standard state agency websites.

Uses the 2-tier crawl pattern (root page + keyword subpages) with
configurable domain filtering. Works for most state board websites.
"""

from __future__ import annotations

from backend.crawlers.base_crawler import BaseCrawler, LinkRecord
from backend.crawlers.config import CrawlTarget


class GenericCrawler(BaseCrawler):
    """
    Default crawler for state agency websites.

    Uses the standard 2-tier HTML crawl pattern:
    1. Fetch root page, extract document links and keyword-matching subpage links
    2. Follow subpage links, extract additional document links
    """

    def discover_links(self, target: CrawlTarget) -> tuple[str, list[LinkRecord]]:
        allowed = target.allowed_domains or None
        return self.two_tier_crawl(target.url, allowed_domains=allowed)
