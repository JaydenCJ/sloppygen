"""The README quickstart must keep working verbatim — code and docs in sync."""

from __future__ import annotations

import json

import pytest

import sloppygen


def test_readme_quickstart_generate():
    # Mirrors the first Quickstart block in README.md.
    sample = sloppygen.generate(
        {"city": "Tokyo", "population_m": 37.4},
        "chatter+trailing_comma",
        seed=7,
    )
    with pytest.raises(json.JSONDecodeError):
        json.loads(sample.text)
    assert sample.expected == {"city": "Tokyo", "population_m": 37.4}
    assert sample.recoverable is True


def test_readme_quickstart_harness():
    # Mirrors the pytest-integration block in README.md.
    payload = sloppygen.synthetic_payload(seed=7)
    samples = sloppygen.corpus(payload, count=62, seed=7)
    report = sloppygen.evaluate(samples, sloppygen.extract_json)
    crashes = [r for r in report.results if r.status == "crash"]
    assert crashes == [], "the baseline must never crash"
