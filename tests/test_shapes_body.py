"""Each body shape must produce exactly the defect it advertises — no more.

The tests parse the corrupted output back where possible, or assert on the
precise substring the mutation introduces, so a shape that starts corrupting
the wrong token fails loudly here.
"""

from __future__ import annotations

import json
import re

import pytest

from sloppygen import generate
from sloppygen.errors import ShapeNotApplicableError


def _gen(payload, shape, seed=42):
    return generate(payload, shape, seed=seed).text


def test_comma_shapes_add_or_remove_exactly_one_comma(payload):
    canonical = json.dumps(payload, indent=2, ensure_ascii=False)
    added = _gen(payload, "trailing_comma")
    assert added.count(",") == canonical.count(",") + 1
    # Removing the comma before a closer restores valid, equal JSON.
    assert json.loads(re.sub(r",(\s*[}\]])", r"\1", added)) == payload
    removed = _gen(payload, "missing_comma")
    assert removed.count(",") == canonical.count(",") - 1
    with pytest.raises(json.JSONDecodeError):
        json.loads(removed)


def test_quote_shapes_follow_their_documented_semantics(payload):
    # single_quotes mimics Python repr(): apostrophe strings keep double quotes.
    text = _gen(payload, "single_quotes")
    assert '"The customer can\'t log in' in text
    assert "'label': 'bug'" in text
    with pytest.raises(json.JSONDecodeError):
        json.loads(text)
    # smart_quotes replaces every delimiter with typographic quotes.
    curly = _gen(payload, "smart_quotes")
    assert '"' not in curly
    assert "“label”" in curly


def test_python_repr_shapes_strip_keys_and_capitalize_literals(payload):
    keys = _gen(payload, "unquoted_keys")
    assert "\n  summary:" in keys and "\n  label:" in keys
    assert '"bug"' in keys  # values keep their quotes
    lits = _gen(payload, "python_literals")
    assert "True" in lits and "None" in lits
    assert "true" not in lits and "null" not in lits


def test_comment_shapes_inject_js_style_comments(payload):
    line = _gen(payload, "line_comment")
    assert "  // " in line
    with pytest.raises(json.JSONDecodeError):
        json.loads(line)
    block = _gen(payload, "block_comment")
    assert block.startswith("{ /* ") and " */" in block


def test_unescaped_newline_lands_inside_a_string_value(payload):
    text = _gen(payload, "unescaped_newline")
    with pytest.raises(json.JSONDecodeError):
        json.loads(text)
    # The break must sit inside a quoted region: an odd number of quotes
    # precedes at least one newline.
    assert any(
        text[:i].count('"') % 2 == 1 for i, ch in enumerate(text) if ch == "\n"
    ), "no newline inside a string value"


def test_number_shapes_nan_destroys_and_nonstandard_preserves(payload):
    nan_text = _gen(payload, "nan_infinity")
    assert any(m in nan_text for m in ("NaN", "Infinity"))
    assert generate(payload, "nan_infinity", seed=42).recoverable is False
    # Each nonstandard spelling keeps the numeric value intact.
    assert "1_234_567" in generate({"n": 1234567}, "nonstandard_numbers", seed=1).text
    assert ": .5" in generate({"n": 0.5}, "nonstandard_numbers", seed=1).text
    assert "-042" in generate({"n": -42}, "nonstandard_numbers", seed=1).text


def test_fullwidth_punct_replaces_structural_chars_only(payload):
    text = _gen(payload, "fullwidth_punct")
    assert "：" in text and "，" in text
    assert "can't log in" in text  # string contents untouched
    with pytest.raises(json.JSONDecodeError):
        json.loads(text)


def test_ellipsis_item_appends_placeholder(payload):
    text = _gen(payload, "ellipsis_item")
    assert ", ..." in text or ", …" in text


def test_jsonl_spray_sprays_arrays_and_refuses_objects(payload, array_payload):
    text = _gen(array_payload, "jsonl_spray")
    lines = text.split("\n")
    assert [json.loads(line) for line in lines] == array_payload
    with pytest.raises(ShapeNotApplicableError):
        generate(payload, "jsonl_spray")


def test_double_encoded_is_valid_json_of_the_wrong_type(payload):
    text = _gen(payload, "double_encoded")
    outer = json.loads(text)                # parses fine...
    assert isinstance(outer, str)           # ...to a string, the trap
    assert json.loads(outer) == payload     # unwrapping once recovers it


def test_repetition_shapes_repeat_and_self_correct(payload):
    canonical = json.dumps(payload, indent=2, ensure_ascii=False)
    doubled = _gen(payload, "duplicate_output")
    assert doubled.count(canonical) == 2
    with pytest.raises(json.JSONDecodeError):
        json.loads(doubled)
    corrected = _gen(payload, "self_correction")
    assert corrected.endswith(canonical)  # the last value is authoritative
    with pytest.raises(json.JSONDecodeError):
        json.loads(corrected.split("\n\n")[0])  # the first attempt is broken


def test_unbalanced_drops_only_the_final_closer(payload):
    text = _gen(payload, "unbalanced")
    with pytest.raises(json.JSONDecodeError):
        json.loads(text)
    # No data was lost: appending the missing closer restores the payload.
    assert json.loads(text + "\n}") == payload


def test_html_escaped_entities_everywhere(payload):
    text = _gen(payload, "html_escaped")
    assert "&quot;" in text
    assert '"' not in text


def test_body_shapes_error_cleanly_on_hostile_payload():
    # A bare number has no strings, no containers, no commas: these shapes
    # must refuse with ShapeNotApplicableError, never corrupt garbage.
    for shape_id in ("trailing_comma", "single_quotes", "unquoted_keys",
                     "missing_comma", "unescaped_newline", "fullwidth_punct"):
        with pytest.raises(ShapeNotApplicableError):
            generate(7, shape_id)
