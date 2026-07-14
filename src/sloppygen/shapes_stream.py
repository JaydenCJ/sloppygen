"""Stream-layer shapes: byte-level damage to the final transcript.

Applied after body mutations and wrappers, exactly where the damage happens
in reality: the model finished (or did not finish) its answer and the
transport layer truncated it, leaked control tokens into it, or salted it
with invisible characters.
"""

from __future__ import annotations

from .registry import MutationContext, Shape
from .textops import string_spans

# Declared in catalog order; assembled by sloppygen.registry, which owns
# the canonical cross-module ordering.
SHAPES = []

_SPECIAL_TOKENS = ("<|im_end|>", "</s>", "<|endoftext|>", "<|eot_id|>", "[DONE]")

_INVISIBLES = ("\u200b", "\u2060", "\u00a0")  # ZWSP, word joiner, NBSP


def _special_tokens(ctx: MutationContext) -> str:
    token = ctx.rng.choice(_SPECIAL_TOKENS)
    sep = ctx.rng.choice(["", "\n"])
    return ctx.text + sep + token


SHAPES.append(Shape(
    id="special_tokens",
    category="wrapper",
    layer="stream",
    recoverable=True,
    description="an end-of-sequence token leaks after the answer",
    note=(
        "Chat-template mismatches let <|im_end|>, </s>, or <|endoftext|> "
        "through as literal text — endemic with self-hosted models behind "
        "OpenAI-compatible proxies."
    ),
    apply=_special_tokens,
))


def _truncated(ctx: MutationContext) -> str:
    frac = ctx.rng.uniform(0.55, 0.92)
    cut = max(1, min(int(len(ctx.text) * frac), len(ctx.text) - 1))
    return ctx.text[:cut]


SHAPES.append(Shape(
    id="truncated",
    category="structure",
    layer="stream",
    recoverable=False,
    description="the transcript stops mid-token at 55-92% of its length",
    note=(
        "max_tokens hit, connection dropped, or a stop sequence fired early. "
        "Data is gone; the only correct parser behaviour is a clean, "
        "explicit failure — never a crash, never a silent partial payload."
    ),
    apply=_truncated,
    applies=lambda ctx: len(ctx.text) >= 20,
))


def _string_cut_points(text: str):
    points = []
    for start, end in string_spans(text):
        if end - start >= 4:
            points.append((start, end))
    return points


def _truncated_string(ctx: MutationContext) -> str:
    start, end = ctx.rng.choice(_string_cut_points(ctx.text))
    cut = start + ctx.rng.randrange(1, end - start)
    return ctx.text[:cut]


SHAPES.append(Shape(
    id="truncated_string",
    category="structure",
    layer="stream",
    recoverable=False,
    description="the transcript stops in the middle of a quoted string",
    note=(
        "The nastiest truncation: the open quote makes the rest of the "
        "document look like string content, defeating bracket-counting "
        "recovery tricks."
    ),
    apply=_truncated_string,
    applies=lambda ctx: bool(_string_cut_points(ctx.text)),
))


def _invisible_chars(ctx: MutationContext) -> str:
    text = ctx.text
    anchors = [i + 1 for i, ch in enumerate(text) if ch in ":,"]
    picks = ctx.rng.sample(anchors, min(len(anchors), ctx.rng.randrange(2, 5)))
    out = []
    for i, ch in enumerate(text):
        out.append(ch)
        if i + 1 in picks:
            out.append(ctx.rng.choice(_INVISIBLES))
    prefix = "\ufeff" if (ctx.rng.random() < 0.5 or not picks) else ""
    return prefix + "".join(out)


SHAPES.append(Shape(
    id="invisible_chars",
    category="noise",
    layer="stream",
    recoverable=True,
    description="zero-width spaces, NBSPs, and a possible BOM sprinkled in",
    note=(
        "Copy-paste chains and web front-ends inject U+200B, U+00A0, and "
        "byte-order marks. The text is visually identical to valid output "
        "and json.loads rejects it with a baffling offset."
    ),
    apply=_invisible_chars,
))
