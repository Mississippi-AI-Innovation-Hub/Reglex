"""
State/agency registry — lookup and filtering helpers for the 21 crawl targets.

7 states (MS, AL, LA, TN, AR, GA, TX) x 3 agency types (medical, real_estate, dental).
"""

from __future__ import annotations

from backend.crawlers.config import ALL_TARGETS, CrawlTarget


# Build lookup dictionaries
_by_state: dict[str, list[CrawlTarget]] = {}
_by_agency: dict[str, list[CrawlTarget]] = {}
_by_key: dict[tuple[str, str], CrawlTarget] = {}

for _t in ALL_TARGETS:
    _by_state.setdefault(_t.state, []).append(_t)
    _by_agency.setdefault(_t.agency_type, []).append(_t)
    _by_key[(_t.state, _t.agency_type)] = _t

STATES = sorted(_by_state.keys())
AGENCY_TYPES = sorted(_by_agency.keys())
REGISTRY = _by_key


def get_targets_for_state(state: str) -> list[CrawlTarget]:
    """Get all targets for a given state code (e.g. 'MS')."""
    return _by_state.get(state.upper(), [])


def get_targets_for_agency_type(agency_type: str) -> list[CrawlTarget]:
    """Get all targets for a given agency type (e.g. 'medical')."""
    return _by_agency.get(agency_type.lower(), [])


def get_target(state: str, agency_type: str) -> CrawlTarget | None:
    """Get a specific target by state + agency_type."""
    return _by_key.get((state.upper(), agency_type.lower()))


def get_all_targets(
    states: list[str] | None = None,
    agency_types: list[str] | None = None,
) -> list[CrawlTarget]:
    """Filter targets by state and/or agency_type."""
    targets = ALL_TARGETS
    if states:
        state_set = {s.upper() for s in states}
        targets = [t for t in targets if t.state in state_set]
    if agency_types:
        agency_set = {a.lower() for a in agency_types}
        targets = [t for t in targets if t.agency_type in agency_set]
    return targets


STATE_NAMES = {
    "MS": "Mississippi",
    "AL": "Alabama",
    "LA": "Louisiana",
    "TN": "Tennessee",
    "AR": "Arkansas",
    "GA": "Georgia",
    "TX": "Texas",
}

AGENCY_TYPE_NAMES = {
    "medical": "Medical Board",
    "real_estate": "Real Estate Commission",
    "dental": "Dental Board",
}
