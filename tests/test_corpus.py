"""Corpus building and JSONL round-trips: coverage, filters, stacking, and
strict validation of files coming back in."""

from __future__ import annotations

import io

import pytest

from sloppygen import corpus
from sloppygen.corpusio import load_corpus, read_jsonl, write_jsonl
from sloppygen.errors import CompositionError, CorpusFormatError
from sloppygen.registry import all_shapes


def test_corpus_cycles_every_applicable_shape_before_repeating(payload):
    samples = corpus(payload, count=30, seed=42)
    first_30_shapes = [s.shapes[0] for s in samples]
    assert len(set(first_30_shapes)) == 30  # jsonl_spray excluded for objects


def test_corpus_includes_jsonl_spray_for_arrays(array_payload):
    samples = corpus(array_payload, count=31, seed=42)
    assert any(s.shapes == ("jsonl_spray",) for s in samples)


def test_corpus_shape_and_category_filters(payload):
    samples = corpus(payload, count=10, seed=1, shapes=["fence", "chatter"])
    assert {s.shapes[0] for s in samples} == {"fence", "chatter"}
    wrappers = corpus(payload, count=12, seed=1, categories=["wrapper"])
    wrapper_ids = {s.id for s in all_shapes(categories=["wrapper"])}
    assert {s.shapes[0] for s in wrappers} <= wrapper_ids


def test_corpus_stacking_combines_layers_in_order(payload):
    layer_of = {s.id: s.layer for s in all_shapes()}
    for s in corpus(payload, count=20, seed=3, stack=2):
        assert len(s.shapes) == 2
        assert layer_of[s.shapes[0]] == "body"
        assert layer_of[s.shapes[1]] in ("wrap", "stream")
    for s in corpus(payload, count=10, seed=3, stack=3):
        assert [layer_of[i] for i in s.shapes] == ["body", "wrap", "stream"]


def test_corpus_rejects_bad_arguments(payload):
    with pytest.raises(CompositionError):
        corpus(payload, count=0)
    with pytest.raises(CompositionError):
        corpus(payload, stack=4)
    with pytest.raises(CompositionError):  # stacking needs body + wrap/stream
        corpus(payload, count=4, stack=2, categories=["wrapper"])


def test_jsonl_round_trip(payload):
    samples = corpus(payload, count=8, seed=42)
    buf = io.StringIO()
    assert write_jsonl(samples, buf) == 8
    buf.seek(0)
    assert read_jsonl(buf) == samples


def test_load_corpus_from_disk(tmp_path, payload):
    path = tmp_path / "c.jsonl"
    with open(path, "w", encoding="utf-8") as fh:
        write_jsonl(corpus(payload, count=5, seed=1), fh)
    assert len(load_corpus(str(path))) == 5


def test_read_jsonl_rejects_malformed_corpora_with_line_numbers():
    good = (
        '{"id": "a", "shapes": ["fence"], "category": "wrapper", '
        '"recoverable": true, "seed": 1, "index": 0, "text": "x", "expected": {}}'
    )
    with pytest.raises(CorpusFormatError, match=r"c\.jsonl:2.*missing"):
        read_jsonl(io.StringIO(good + "\n" + '{"id": "b"}\n'), source="c.jsonl")
    with pytest.raises(CorpusFormatError, match=r"bad\.jsonl:1"):
        read_jsonl(io.StringIO("not json\n"), source="bad.jsonl")
    with pytest.raises(CorpusFormatError, match="expected a JSON object"):
        read_jsonl(io.StringIO("[1, 2]\n"))
    with pytest.raises(CorpusFormatError, match="empty"):
        read_jsonl(io.StringIO("\n\n"))
