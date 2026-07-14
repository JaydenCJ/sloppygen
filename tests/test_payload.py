"""Synthetic payloads must be rich enough that every body shape applies —
otherwise default corpora silently lose coverage."""

from __future__ import annotations

import json

import pytest

from sloppygen import synthetic_payload
from sloppygen.engine import applicable_shapes
from sloppygen.errors import PayloadError
from sloppygen.payload import load_payload
from sloppygen.registry import all_shapes


def test_synthetic_payloads_enable_the_documented_shape_pools():
    for seed in (1, 42, 999):
        pool = {s.id for s in applicable_shapes(synthetic_payload(seed=seed))}
        expected = {s.id for s in all_shapes()} - {"jsonl_spray"}
        assert pool == expected, f"seed {seed}"
    array_pool = {s.id for s in applicable_shapes(synthetic_payload(seed=42, kind="array"))}
    assert "jsonl_spray" in array_pool


def test_synthetic_payload_is_serializable_with_apostrophes_and_unicode():
    payload = synthetic_payload(seed=7)
    assert json.loads(json.dumps(payload)) == payload
    # Apostrophes exercise single_quotes' repr()-style dual quoting; unicode
    # keeps encoders honest about ensure_ascii.
    text = json.dumps(synthetic_payload(seed=42), ensure_ascii=False)
    assert "'" in text


def test_unknown_synthetic_kind_raises():
    with pytest.raises(PayloadError):
        synthetic_payload(seed=1, kind="scalar")


def test_load_payload_reads_a_file(tmp_path):
    path = tmp_path / "p.json"
    path.write_text('{"a": [1, 2]}', encoding="utf-8")
    assert load_payload(str(path)) == {"a": [1, 2]}


def test_load_payload_rejects_bad_sources(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("{oops}", encoding="utf-8")
    with pytest.raises(PayloadError, match="not valid JSON"):
        load_payload(str(bad))
    with pytest.raises(PayloadError, match="cannot read"):
        load_payload("/nonexistent/nowhere.json")
