"""The tokenizer is the foundation every body shape stands on: it must
round-trip valid JSON byte-for-byte and classify tokens precisely, or a
mutation could corrupt something it did not mean to touch."""

from __future__ import annotations

import json

import pytest

from sloppygen.textops import (
    container_close_spots,
    render,
    scan_balanced,
    string_spans,
    strings,
    structural,
    tokenize,
)

DOC = '{"name": "Ada \\"the first\\" Lovelace", "n": -1.5e3, "ok": true, "x": null, "list": [1, 2]}'


def test_tokenize_round_trips_byte_identically():
    assert render(tokenize(DOC)) == DOC
    pretty = json.dumps(json.loads(DOC), indent=2)
    assert render(tokenize(pretty)) == pretty


def test_tokenize_classifies_strings_numbers_and_literals():
    toks = tokenize(DOC)
    # A string with escaped quotes is one token, not three.
    assert '"Ada \\"the first\\" Lovelace"' in [t.text for t in toks if t.kind == "string"]
    # Sign and exponent belong to the number token.
    assert "-1.5e3" in [t.text for t in toks if t.kind == "number"]
    literals = [(t.kind, t.text) for t in toks if t.kind == "literal"]
    assert ("literal", "true") in literals and ("literal", "null") in literals


def test_object_keys_are_marked_and_values_are_not():
    toks = tokenize(DOC)
    assert {json.loads(t.text) for t in strings(toks, keys=True)} == {"name", "n", "ok", "x", "list"}
    assert {json.loads(t.text) for t in strings(toks, keys=False)} == {'Ada "the first" Lovelace'}


def test_structural_filters_punctuation_exactly():
    toks = tokenize(DOC)
    assert len(structural(toks, ",")) == DOC.count(",")
    assert all(t.text == ":" for t in structural(toks, ":"))


def test_tokenize_rejects_garbage_and_unterminated_strings():
    with pytest.raises(ValueError):
        tokenize("{'single': @}")
    with pytest.raises(ValueError):
        tokenize('{"open": "never closed')


def test_container_close_spots_point_after_the_last_element():
    text = '{"a": [1, 2]}'
    spots = container_close_spots(tokenize(text))
    # One spot after `2` (array) and one after `]` (object)...
    assert spots == [text.index("2") + 1, text.index("]") + 1]
    # ...and empty containers offer no spot at all.
    assert container_close_spots(tokenize("{}")) == []
    assert container_close_spots(tokenize("[]")) == []


def test_scan_balanced_matches_closers_and_reports_truncation():
    text = 'noise {"a": {"b": "}"}} trailing'
    start = text.index("{")
    end = scan_balanced(text, start)
    # Braces inside strings must not confuse the scanner.
    assert json.loads(text[start:end]) == {"a": {"b": "}"}}
    assert scan_balanced('{"a": [1, 2', 0) == -1


def test_string_spans_on_arbitrary_prose_skips_unclosed_quotes():
    text = 'He said "hello there" and "bye'
    spans = string_spans(text)
    assert len(spans) == 1
    assert text[spans[0][0]:spans[0][1]] == "hello there"
