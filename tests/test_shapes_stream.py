"""Stream shapes damage the final transcript the way transports do:
truncation loses data (and must say so via recoverable=False), leaked
tokens and invisible bytes do not."""

from __future__ import annotations

import json

from sloppygen import generate
from sloppygen.shapes_stream import _SPECIAL_TOKENS


def _canonical(payload):
    return json.dumps(payload, indent=2, ensure_ascii=False)


def test_special_tokens_appends_a_known_terminator(payload):
    text = generate(payload, "special_tokens", seed=1).text
    assert any(text.endswith(tok) for tok in _SPECIAL_TOKENS)
    assert _canonical(payload) in text


def test_truncated_is_a_strict_prefix_within_cut_bounds(payload):
    canonical = _canonical(payload)
    for i in range(10):
        sample = generate(payload, "truncated", seed=9, index=i)
        assert canonical.startswith(sample.text)
        frac = len(sample.text) / len(canonical)
        assert 0.5 <= frac < 0.95, f"index {i}: cut at {frac:.2f}"
        assert sample.recoverable is False


def test_truncated_string_cuts_inside_a_quoted_region(payload):
    sample = generate(payload, "truncated_string", seed=1)
    # An odd number of quotes means the last string never closed.
    assert sample.text.count('"') % 2 == 1
    assert sample.recoverable is False


def test_invisible_chars_are_invisible_but_fatal(payload):
    for i in range(20):
        text = generate(payload, "invisible_chars", seed=4, index=i).text
        assert text != _canonical(payload), f"index {i} produced clean output"
        stripped = text.lstrip("\ufeff")
        for ch in ("\u200b", "\u2060", "\u00a0"):
            stripped = stripped.replace(ch, "")
        # Removing the invisible bytes restores the exact canonical document.
        assert stripped == _canonical(payload)
