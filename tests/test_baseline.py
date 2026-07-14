"""The reference extractor's contract: recover what it claims to recover,
reject cleanly (ValueError) on what it does not, and never raise anything
else. Its known blind spot — Python's json accepting NaN — is pinned too."""

from __future__ import annotations

import json
import math

import pytest

from sloppygen import extract_json, generate
from sloppygen.registry import all_shapes

# Shapes the baseline is documented to survive (see src/sloppygen/baseline.py).
_RECOVERED_BY_BASELINE = (
    "fence",
    "fence_unclosed",
    "fence_wrong_lang",
    "chatter",
    "prose_inside_fence",
    "tag_wrap",
    "thinking_leak",
    "special_tokens",
    "trailing_comma",
    "duplicate_output",
    "self_correction",
    "invisible_chars",
)


def test_baseline_recovers_its_documented_shapes(payload):
    for shape_id in _RECOVERED_BY_BASELINE:
        for i in range(3):  # three rng variants each, e.g. all chatter modes
            sample = generate(payload, shape_id, seed=13, index=i)
            assert extract_json(sample.text) == payload, f"{shape_id} index {i}"


def test_baseline_rejects_truncation_with_a_clear_message(payload):
    sample = generate(payload, "truncated", seed=13)
    with pytest.raises(ValueError, match="truncated or unbalanced"):
        extract_json(sample.text)


def test_baseline_rejects_syntax_mutations_it_does_not_repair(payload):
    for shape_id in ("single_quotes", "python_literals", "smart_quotes",
                     "fullwidth_punct", "html_escaped"):
        sample = generate(payload, shape_id, seed=13)
        with pytest.raises(ValueError):
            extract_json(sample.text)


def test_baseline_never_raises_anything_but_valueerror(payload):
    # The whole catalog, three variants each: any non-ValueError exception
    # would make the baseline a crash in its own harness.
    for shape in all_shapes():
        if shape.id == "jsonl_spray":
            continue
        for i in range(3):
            sample = generate(payload, shape.id, seed=29, index=i)
            try:
                extract_json(sample.text)
            except ValueError:
                pass


def test_baseline_known_flaw_nan_parses_to_nan(payload):
    # Documented on purpose: json.loads accepts NaN/Infinity, so the
    # baseline returns a payload with a NaN where a number should be —
    # a "wrong", not a rejection. This is the bug class the shape exists for.
    sample = generate(payload, "nan_infinity", seed=13)
    value = extract_json(sample.text)
    assert any(
        isinstance(v, float) and (math.isnan(v) or math.isinf(v))
        for v in _walk_numbers(value)
    )


def _walk_numbers(value):
    if isinstance(value, dict):
        for v in value.values():
            yield from _walk_numbers(v)
    elif isinstance(value, list):
        for v in value:
            yield from _walk_numbers(v)
    elif isinstance(value, (int, float)):
        yield value


def test_baseline_passes_valid_json_and_rejects_pure_prose(payload):
    assert extract_json(json.dumps(payload)) == payload
    with pytest.raises(ValueError, match="no JSON object or array"):
        extract_json("I could not find any structured data in the input.")
