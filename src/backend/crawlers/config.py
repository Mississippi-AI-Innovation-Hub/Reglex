"""
Crawler configuration — defines all 21 crawl targets across 7 states and 3 agency types.

All targets now point to official Secretary of State or state-designated
administrative code sources per client directive (2026-03-25).

States: MS, AL, LA, TN, AR, GA, TX
Agency Types: medical, real_estate, dental
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class CrawlTarget:
    """A single crawl target (one state + one agency type)."""
    state: str                      # e.g. "MS", "TN", "TX"
    agency_type: str                # "medical", "real_estate", "dental"
    agency_name: str                # Full name, e.g. "Tennessee Board of Dentistry"
    url: str                        # Root page to crawl
    crawler_type: str = "generic"   # "generic", "ms_sos", "tn_sos", "al_admin", "la_doa", "ar_sos", "ga_sos", "tx_sos"
    allowed_domains: tuple[str, ...] = ()  # Domains to follow for subpage crawl
    extra: dict = field(default_factory=dict)  # Crawler-specific config


# ── Mississippi (POST-based SOS API pattern) ────────────────────────────

MS_TARGETS = [
    CrawlTarget(
        state="MS",
        agency_type="medical",
        agency_name="Mississippi State Board of Medical Licensure",
        url="https://www.sos.ms.gov/adminsearch/default.aspx",
        crawler_type="ms_sos",
        extra={"agency_id": "90"},  # Title 30 - STATE BOARD OF MEDICAL LICENSURE
    ),
    CrawlTarget(
        state="MS",
        agency_type="real_estate",
        agency_name="Mississippi Real Estate Commission",
        url="https://www.sos.ms.gov/adminsearch/default.aspx",
        crawler_type="ms_sos",
        extra={"agency_id": "51"},  # Title 30 - REAL ESTATE COMMISSION
    ),
    CrawlTarget(
        state="MS",
        agency_type="dental",
        agency_name="Mississippi State Board of Dental Examiners",
        url="https://www.sos.ms.gov/adminsearch/default.aspx",
        crawler_type="ms_sos",
        extra={"agency_id": "60"},  # Title 30 - STATE BOARD OF DENTAL EXAMINERS
    ),
]

# ── Tennessee (SoS Division of Publications — static PDF index) ────────

TN_TARGETS = [
    CrawlTarget(
        state="TN",
        agency_type="medical",
        agency_name="Tennessee Board of Medical Examiners",
        url="https://publications.tnsosfiles.com/rules/0880/0880.htm",
        crawler_type="tn_sos",
        allowed_domains=("publications.tnsosfiles.com",),
        extra={"code": "0880"},
    ),
    CrawlTarget(
        state="TN",
        agency_type="real_estate",
        agency_name="Tennessee Real Estate Commission",
        url="https://publications.tnsosfiles.com/rules/1260/1260.htm",
        crawler_type="tn_sos",
        allowed_domains=("publications.tnsosfiles.com",),
        extra={"code": "1260"},
    ),
    CrawlTarget(
        state="TN",
        agency_type="dental",
        agency_name="Tennessee Board of Dentistry",
        url="https://publications.tnsosfiles.com/rules/0460/0460.htm",
        crawler_type="tn_sos",
        allowed_domains=("publications.tnsosfiles.com",),
        extra={"code": "0460"},
    ),
]

# ── Alabama (Legislative Services Agency — REST PDF endpoints) ─────────

AL_TARGETS = [
    CrawlTarget(
        state="AL",
        agency_type="medical",
        agency_name="Alabama Board of Medical Examiners",
        url="https://admincode.legislature.state.al.us/",
        crawler_type="al_admin",
        extra={
            "agency_number": "540",
            "chapters": [
                "540-X-1", "540-X-2", "540-X-3", "540-X-4", "540-X-5",
                "540-X-6", "540-X-7", "540-X-8", "540-X-9", "540-X-10",
                "540-X-11", "540-X-12", "540-X-13", "540-X-14", "540-X-15",
                "540-X-16", "540-X-17", "540-X-18", "540-X-19", "540-X-20",
                "540-X-21", "540-X-22", "540-X-23", "540-X-24", "540-X-25",
            ],
        },
    ),
    CrawlTarget(
        state="AL",
        agency_type="real_estate",
        agency_name="Alabama Real Estate Commission",
        url="https://admincode.legislature.state.al.us/",
        crawler_type="al_admin",
        extra={
            "agency_number": "790",
            "chapters": [
                "790-X-1", "790-X-2", "790-X-3", "790-X-4",
            ],
        },
    ),
    CrawlTarget(
        state="AL",
        agency_type="dental",
        agency_name="Alabama Board of Dental Examiners",
        url="https://admincode.legislature.state.al.us/",
        crawler_type="al_admin",
        extra={
            "agency_number": "270",
            "chapters": [
                "270-X-1", "270-X-2", "270-X-3", "270-X-4", "270-X-5",
            ],
        },
    ),
]

# ── Louisiana (Division of Administration / OSR — DOCX downloads) ──────

LA_TARGETS = [
    CrawlTarget(
        state="LA",
        agency_type="medical",
        agency_name="Louisiana State Board of Medical Examiners",
        url="https://www.doa.la.gov/doa/osr/louisiana-administrative-code/",
        crawler_type="la_doa",
        extra={
            "title": "46",
            "part": "XLV",
            "volume_file": "46v45",
        },
    ),
    CrawlTarget(
        state="LA",
        agency_type="real_estate",
        agency_name="Louisiana Real Estate Commission",
        url="https://www.doa.la.gov/doa/osr/louisiana-administrative-code/",
        crawler_type="la_doa",
        extra={
            "title": "46",
            "part": "LXVII",
            "volume_file": "46v67",
        },
    ),
    CrawlTarget(
        state="LA",
        agency_type="dental",
        agency_name="Louisiana State Board of Dentistry",
        url="https://www.doa.la.gov/doa/osr/louisiana-administrative-code/",
        crawler_type="la_doa",
        extra={
            "title": "46",
            "part": "XXXIII",
            "volume_file": "46v33",
        },
    ),
]

# ── Arkansas (SoS Rules & Regulations — POST + S3 PDFs) ───────────────

AR_TARGETS = [
    CrawlTarget(
        state="AR",
        agency_type="medical",
        agency_name="Arkansas State Medical Board",
        url="https://www.sos.arkansas.gov/rules-regulations",
        crawler_type="ar_sos",
        extra={
            "search_url": "https://sos-rules-reg.ark.org/rules/search",
            "agency_id": "A239_332",
            "alt_agency_id": "A59",
        },
    ),
    CrawlTarget(
        state="AR",
        agency_type="real_estate",
        agency_name="Arkansas Real Estate Commission",
        url="https://www.sos.arkansas.gov/rules-regulations",
        crawler_type="ar_sos",
        extra={
            "search_url": "https://sos-rules-reg.ark.org/rules/search",
            "agency_id": "A235_285",
            "alt_agency_id": "A76",
        },
    ),
    CrawlTarget(
        state="AR",
        agency_type="dental",
        agency_name="Arkansas State Board of Dental Examiners",
        url="https://www.sos.arkansas.gov/rules-regulations",
        crawler_type="ar_sos",
        extra={
            "search_url": "https://sos-rules-reg.ark.org/rules/search",
            "agency_id": "A38",
        },
    ),
]

# ── Georgia (SoS Administrative Procedure Division) ───────────────────

GA_TARGETS = [
    CrawlTarget(
        state="GA",
        agency_type="medical",
        agency_name="Georgia Composite Medical Board",
        url="https://rules.sos.ga.gov/gac/360",
        crawler_type="ga_sos",
        allowed_domains=("rules.sos.ga.gov",),
        extra={"dept": "360"},
    ),
    CrawlTarget(
        state="GA",
        agency_type="real_estate",
        agency_name="Georgia Real Estate Commission",
        url="https://rules.sos.ga.gov/gac/520",
        crawler_type="ga_sos",
        allowed_domains=("rules.sos.ga.gov",),
        extra={"dept": "520"},
    ),
    CrawlTarget(
        state="GA",
        agency_type="dental",
        agency_name="Georgia Board of Dentistry",
        url="https://rules.sos.ga.gov/gac/150",
        crawler_type="ga_sos",
        allowed_domains=("rules.sos.ga.gov",),
        extra={"dept": "150"},
    ),
]

# ── Texas (SoS Texas Administrative Code — HTML pages) ────────────────

TX_TARGETS = [
    CrawlTarget(
        state="TX",
        agency_type="medical",
        agency_name="Texas Medical Board",
        url="https://texas-sos.appianportalsgov.com/rules-and-meetings",
        crawler_type="tx_sos",
        allowed_domains=("texas-sos.appianportalsgov.com", "texas-sos.appianportalsgov-dynamic.com"),
        extra={"title": "22", "part": "9"},
    ),
    CrawlTarget(
        state="TX",
        agency_type="real_estate",
        agency_name="Texas Real Estate Commission",
        url="https://texas-sos.appianportalsgov.com/rules-and-meetings",
        crawler_type="tx_sos",
        allowed_domains=("texas-sos.appianportalsgov.com", "texas-sos.appianportalsgov-dynamic.com"),
        extra={"title": "22", "part": "23"},
    ),
    CrawlTarget(
        state="TX",
        agency_type="dental",
        agency_name="Texas State Board of Dental Examiners",
        url="https://texas-sos.appianportalsgov.com/rules-and-meetings",
        crawler_type="tx_sos",
        allowed_domains=("texas-sos.appianportalsgov.com", "texas-sos.appianportalsgov-dynamic.com"),
        extra={"title": "22", "part": "5"},
    ),
]

# ── All targets ─────────────────────────────────────────────────────────

ALL_TARGETS: list[CrawlTarget] = (
    MS_TARGETS + TN_TARGETS + AL_TARGETS + LA_TARGETS
    + AR_TARGETS + GA_TARGETS + TX_TARGETS
)


@dataclass
class CrawlerConfig:
    """Global crawler configuration."""
    dest_root: str = "./crawled_documents"
    s3_bucket: str = "ms-sos-legal-documents"
    s3_prefix: str = "crawled-documents"
    timeout_s: float = 30.0
    max_subpages: int = 20
    retries: int = 2
    targets: list[CrawlTarget] = field(default_factory=lambda: list(ALL_TARGETS))
