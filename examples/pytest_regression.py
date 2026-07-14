#!/usr/bin/env python3
"""Drop-in pytest regression suite for your own extractor.

Copy this file into your test tree, point ``parse`` at your extractor, and
every documented LLM failure shape becomes a permanent regression test —
deterministic, offline, no fixtures to maintain.

    python3 -m pytest examples/pytest_regression.py
"""

import pytest

import sloppygen
from sloppygen import extract_json as parse  # <- replace with your parser

PAYLOAD = sloppygen.synthetic_payload(seed=2026)
SAMPLES = sloppygen.corpus(PAYLOAD, count=62, seed=2026)


@pytest.mark.parametrize("sample", SAMPLES, ids=lambda s: s.id)
def test_parser_never_crashes(sample):
    """The one guarantee every parser owes its callers: fail cleanly."""
    try:
        parse(sample.text)
    except ValueError:
        pass  # a clean rejection is acceptable; a crash is not


@pytest.mark.parametrize(
    "sample",
    [s for s in SAMPLES if s.shapes[0] in ("fence", "chatter", "fence_unclosed")],
    ids=lambda s: s.id,
)
def test_parser_recovers_the_easy_wrappers(sample):
    """Wrapper noise is table stakes: the payload must come back intact."""
    assert parse(sample.text) == sample.expected
