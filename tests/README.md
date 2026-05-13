# `tests/`

The PoC's primary validation surface is the evaluation suite in
`evaluation/`, not unit tests. Two test-style files do ship with the
codebase:

- `evaluation/test_judge.py` — exercises the 4-axis judge prompts.
- (Reserved for future unit tests of the agents, crawlers, and
  ingestion pipeline.)

If you add unit tests here, prefer `pytest` and keep them fast — the
agent tests should mock Bedrock rather than hit it.
