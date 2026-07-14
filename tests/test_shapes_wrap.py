"""Wrap shapes must leave the JSON body byte-intact — that is their contract:
they are recoverable precisely because the payload survives inside the noise."""

from __future__ import annotations

import json

from sloppygen import generate
from sloppygen.registry import all_shapes
from sloppygen.shapes_wrap import POSTAMBLES, PREAMBLES


def _canonical(payload):
    return json.dumps(payload, indent=2, ensure_ascii=False)


def test_every_wrap_shape_preserves_the_body_verbatim(payload):
    for shape in all_shapes(layers=["wrap"]):
        text = generate(payload, shape, seed=3).text
        assert _canonical(payload) in text, shape.id


def test_fence_variants_open_close_stutter_and_trailing_prose(payload):
    fenced = generate(payload, "fence", seed=1).text
    assert fenced.startswith("```json\n") and fenced.endswith("\n```")
    unclosed = generate(payload, "fence_unclosed", seed=1).text
    assert unclosed.count("```") == 1
    stuttered = generate(payload, "fence_double", seed=1).text
    assert stuttered.startswith("```json\n```json\n")
    # prose_inside_fence: the sentence sits after the JSON, before the closer.
    prosed = generate(payload, "prose_inside_fence", seed=1).text
    assert prosed[: prosed.rindex("```")].rstrip().endswith(".")


def test_fence_wrong_lang_never_uses_plain_json_tag(payload):
    # 40 indices cover the whole language pool; none may be exactly "json".
    for i in range(40):
        first_line = generate(payload, "fence_wrong_lang", seed=1, index=i).text.split("\n", 1)[0]
        assert first_line.startswith("```") and first_line != "```json", f"index {i}"


def test_chatter_draws_from_the_documented_pools(payload):
    seen_pre, seen_post = False, False
    for i in range(30):
        text = generate(payload, "chatter", seed=5, index=i).text
        seen_pre = seen_pre or any(text.startswith(p) for p in PREAMBLES)
        seen_post = seen_post or any(text.endswith(p) for p in POSTAMBLES)
    assert seen_pre and seen_post


def test_tag_wrap_uses_known_tags_and_sometimes_forgets_to_close(payload):
    outcomes = set()
    for i in range(40):
        text = generate(payload, "tag_wrap", seed=2, index=i).text
        assert text.split("\n", 1)[0] in (
            "<json>", "<answer>", "<output>", "<result>", "<response>"
        )
        outcomes.add("</" in text[-15:])
    assert outcomes == {True, False}, "both closed and unclosed variants must occur"


def test_thinking_leak_block_precedes_the_json(payload):
    text = generate(payload, "thinking_leak", seed=1).text
    assert text.startswith("<thinking>\n")
    assert text.index("</thinking>") < text.index("{")
