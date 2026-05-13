# `data/sample/`

This directory is intentionally empty.

Per the Innovation Hub publication standard, **no real agency data
ships in this repository**. The crawlers in
`src/backend/crawlers/` pull public regulatory documents directly from
each source agency at ingestion time.

If you add sample documents here for local smoke-testing, make sure they
are:

- Synthetic or clearly-fake (not real agency records).
- Small (a few KB each is enough for a smoke test).
- Free of any personal information, contact details, or proprietary
  third-party content.

See `docs/data-notes.md` for the full data policy.
