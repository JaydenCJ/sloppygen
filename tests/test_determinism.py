"""The flagship guarantee: same inputs, same bytes — on any machine.

A corpus is defined by (version, seed, payload, options). If any of these
tests fail, published corpora stop being reproducible and the whole
regression-testing story collapses.
"""

from __future__ import annotations

import io

from sloppygen import corpus, generate, synthetic_payload
from sloppygen.corpusio import write_jsonl
from sloppygen.rng import derive_rng


def test_generate_is_byte_identical_and_matches_the_golden_value(payload):
    a = generate(payload, "chatter", seed=42, index=3)
    b = generate(payload, "chatter", seed=42, index=3)
    assert a.text == b.text
    # A frozen golden value: if this changes, determinism broke — or the rng
    # derivation changed, which is a breaking change that must be published.
    assert generate({"ok": True}, "fence", seed=42).text == '```json\n{\n  "ok": true\n}\n```'


def test_seed_and_index_both_rekey_the_stream(payload):
    assert generate(payload, "chatter", seed=1).text != generate(payload, "chatter", seed=2).text
    texts = {generate(payload, "truncated", seed=7, index=i).text for i in range(8)}
    assert len(texts) > 1, "index must re-key the random stream"


def test_shape_stack_rekeys_the_stream(payload):
    # The same seed/index with a different stack must not reuse the stream.
    solo = generate(payload, "chatter", seed=3).text
    stacked = generate(payload, "trailing_comma+chatter", seed=3).text
    assert solo not in stacked


def test_corpus_serialization_is_byte_identical(payload):
    buf_a, buf_b = io.StringIO(), io.StringIO()
    write_jsonl(corpus(payload, count=40, seed=42), buf_a)
    write_jsonl(corpus(payload, count=40, seed=42), buf_b)
    assert buf_a.getvalue() == buf_b.getvalue()


def test_synthetic_payload_is_deterministic():
    assert synthetic_payload(seed=42) == synthetic_payload(seed=42)
    assert synthetic_payload(seed=42) != synthetic_payload(seed=43)


def test_derive_rng_streams_are_independent_and_collision_free():
    a = derive_rng(1, 0, "chatter")
    b = derive_rng(1, 1, "chatter")
    c = derive_rng(1, 0, "chatter")
    seq = lambda r: [r.random() for _ in range(4)]  # noqa: E731
    seq_a, seq_b, seq_c = seq(a), seq(b), seq(c)
    assert seq_a == seq_c and seq_a != seq_b
    # ("ab", "c") and ("a", "bc") must key different streams.
    assert derive_rng(1, "ab", "c").random() != derive_rng(1, "a", "bc").random()
