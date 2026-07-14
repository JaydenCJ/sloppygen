"""Body-layer shapes: token-aware mutations of the JSON text itself.

Every function here receives the *canonical* serialization of the payload
(valid, pretty-printed JSON) and returns a corrupted variant. Mutations go
through the tokenizer in :mod:`sloppygen.textops`, so they touch exactly the
tokens they claim to touch — a re-quoted string is a real string token, a
dropped comma is a structural comma, never a comma inside a value.
"""

from __future__ import annotations

import json
import re

from .registry import MutationContext, Shape
from .textops import (
    container_close_spots,
    iter_lines_with_offsets,
    numbers,
    splice,
    strings,
    structural,
    tokenize,
)

# Declared in catalog order; assembled by sloppygen.registry, which owns
# the canonical cross-module ordering.
SHAPES = []

_IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")

_COMMENTS = (
    "TODO: confirm with the user",
    "inferred from context",
    "added as requested",
    "see the notes above",
    "approximate value",
)

_CORRECTIONS = (
    "Wait, I made a syntax error in the JSON above. Here is the corrected version:",
    "Apologies — the previous output was malformed. Corrected JSON:",
    "Actually, let me fix that. The valid JSON is:",
)


# --------------------------------------------------------------------------
# syntax category
# --------------------------------------------------------------------------

def _trailing_comma_spots(text: str):
    return container_close_spots(tokenize(text))


def _apply_trailing_comma(ctx: MutationContext) -> str:
    spots = _trailing_comma_spots(ctx.text)
    pos = ctx.rng.choice(spots)
    return splice(ctx.text, pos, pos, ",")


SHAPES.append(Shape(
    id="trailing_comma",
    category="syntax",
    layer="body",
    recoverable=True,
    description="a comma after the last element of an object or array",
    note=(
        "The single most common JSON defect in model output: the model emits "
        "elements in a loop and closes the container without removing the "
        "final separator, exactly like a human writing JavaScript."
    ),
    apply=_apply_trailing_comma,
    applies=lambda ctx: bool(_trailing_comma_spots(ctx.text)),
))


def _apply_missing_comma(ctx: MutationContext) -> str:
    commas = structural(tokenize(ctx.text), ",")
    tok = ctx.rng.choice(commas)
    return splice(ctx.text, tok.start, tok.end, "")


SHAPES.append(Shape(
    id="missing_comma",
    category="syntax",
    layer="body",
    recoverable=True,
    description="one structural comma between elements is dropped",
    note=(
        "Long generations occasionally skip a separator token, most often "
        "right after a line break between object members."
    ),
    apply=_apply_missing_comma,
    applies=lambda ctx: bool(structural(tokenize(ctx.text), ",")),
))


def _single_quotable(text: str):
    out = []
    for tok in strings(tokenize(text)):
        if "'" not in json.loads(tok.text):
            out.append(tok)
    return out


def _apply_single_quotes(ctx: MutationContext) -> str:
    # Mimic Python's repr(): strings gain single quotes unless the content
    # itself contains an apostrophe, in which case repr() keeps double quotes.
    pieces = []
    for tok in tokenize(ctx.text):
        if tok.kind == "string" and "'" not in json.loads(tok.text):
            inner = tok.text[1:-1].replace('\\"', '"')
            pieces.append("'" + inner + "'")
        else:
            pieces.append(tok.text)
    return "".join(pieces)


SHAPES.append(Shape(
    id="single_quotes",
    category="syntax",
    layer="body",
    recoverable=True,
    description="strings quoted with ' instead of \", Python-dict style",
    note=(
        "Produced whenever a model narrates a Python dict instead of JSON — "
        "typically after code-heavy prompts. Strings containing an apostrophe "
        "keep double quotes, exactly as Python's repr() would print them."
    ),
    apply=_apply_single_quotes,
    applies=lambda ctx: bool(_single_quotable(ctx.text)),
))


def _bare_keys(text: str):
    out = []
    for tok in strings(tokenize(text), keys=True):
        if _IDENTIFIER.match(json.loads(tok.text)):
            out.append(tok)
    return out


def _apply_unquoted_keys(ctx: MutationContext) -> str:
    pieces = []
    for tok in tokenize(ctx.text):
        if tok.kind == "string" and tok.is_key:
            key = json.loads(tok.text)
            if isinstance(key, str) and _IDENTIFIER.match(key):
                pieces.append(key)
                continue
        pieces.append(tok.text)
    return "".join(pieces)


SHAPES.append(Shape(
    id="unquoted_keys",
    category="syntax",
    layer="body",
    recoverable=True,
    description="identifier-like object keys lose their quotes ({key: ...})",
    note=(
        "JavaScript object-literal syntax bleeding into JSON output; every "
        "key that is a valid identifier is emitted bare."
    ),
    apply=_apply_unquoted_keys,
    applies=lambda ctx: bool(_bare_keys(ctx.text)),
))


_PY_LITERALS = {"true": "True", "false": "False", "null": "None"}


def _apply_python_literals(ctx: MutationContext) -> str:
    pieces = []
    for tok in tokenize(ctx.text):
        if tok.kind == "literal":
            pieces.append(_PY_LITERALS[tok.text])
        else:
            pieces.append(tok.text)
    return "".join(pieces)


SHAPES.append(Shape(
    id="python_literals",
    category="syntax",
    layer="body",
    recoverable=True,
    description="True / False / None instead of true / false / null",
    note=(
        "The signature of a model reciting a Python object: capitalized "
        "booleans and None survive into what is otherwise JSON."
    ),
    apply=_apply_python_literals,
    applies=lambda ctx: any(t.kind == "literal" for t in tokenize(ctx.text)),
))


def _apply_smart_quotes(ctx: MutationContext) -> str:
    pieces = []
    for tok in tokenize(ctx.text):
        if tok.kind == "string":
            pieces.append("“" + tok.text[1:-1] + "”")
        else:
            pieces.append(tok.text)
    return "".join(pieces)


SHAPES.append(Shape(
    id="smart_quotes",
    category="syntax",
    layer="body",
    recoverable=True,
    description='typographic “quotes” replace every straight " delimiter',
    note=(
        "Appears when output round-trips through chat UIs, documents, or "
        "training data with typographic substitution; the JSON looks perfect "
        "to a human and is unparseable to a machine."
    ),
    apply=_apply_smart_quotes,
    applies=lambda ctx: bool(strings(tokenize(ctx.text))),
))


def _comment_lines(text: str):
    out = []
    for offset, line in iter_lines_with_offsets(text):
        if line.rstrip().endswith(("{", "[", ",")):
            out.append(offset + len(line))
    return out


def _apply_line_comment(ctx: MutationContext) -> str:
    ends = _comment_lines(ctx.text)
    pos = ctx.rng.choice(ends)
    comment = ctx.rng.choice(_COMMENTS)
    return splice(ctx.text, pos, pos, "  // " + comment)


SHAPES.append(Shape(
    id="line_comment",
    category="syntax",
    layer="body",
    recoverable=True,
    description="a // comment appended to one line of the JSON",
    note=(
        "Models asked to 'annotate' or 'explain' their output frequently "
        "inline the explanation as JavaScript-style comments."
    ),
    apply=_apply_line_comment,
    applies=lambda ctx: bool(_comment_lines(ctx.text)),
))


def _apply_block_comment(ctx: MutationContext) -> str:
    comment = ctx.rng.choice(_COMMENTS)
    return splice(ctx.text, 1, 1, " /* " + comment + " */")


SHAPES.append(Shape(
    id="block_comment",
    category="syntax",
    layer="body",
    recoverable=True,
    description="a /* block comment */ right after the opening brace",
    note=(
        "The JSON5/JSONC habit: a header comment inside the container, "
        "common when models mimic configuration-file examples."
    ),
    apply=_apply_block_comment,
    applies=lambda ctx: ctx.text[:1] in ("{", "["),
))


def _newline_hosts(text: str):
    out = []
    for tok in strings(tokenize(text), keys=False):
        value = json.loads(tok.text)
        if isinstance(value, str) and len(value) >= 12 and " " in value[3:-3]:
            out.append(tok)
    return out


def _apply_unescaped_newline(ctx: MutationContext) -> str:
    tok = ctx.rng.choice(_newline_hosts(ctx.text))
    inner = tok.text[1:-1]
    space_positions = [i for i, ch in enumerate(inner) if ch == " " and 3 <= i <= len(inner) - 4]
    cut = ctx.rng.choice(space_positions)
    mutated = '"' + inner[:cut] + "\n" + inner[cut + 1:] + '"'
    return splice(ctx.text, tok.start, tok.end, mutated)


SHAPES.append(Shape(
    id="unescaped_newline",
    category="syntax",
    layer="body",
    recoverable=True,
    description="a raw line break inside a string value instead of \\n",
    note=(
        "Multi-sentence field values get emitted with literal newlines; "
        "strict JSON forbids control characters inside strings, so the value "
        "splits the document across lines."
    ),
    apply=_apply_unescaped_newline,
    applies=lambda ctx: bool(_newline_hosts(ctx.text)),
))


def _apply_nan_infinity(ctx: MutationContext) -> str:
    tok = ctx.rng.choice(numbers(tokenize(ctx.text)))
    replacement = ctx.rng.choice(["NaN", "Infinity", "-Infinity"])
    return splice(ctx.text, tok.start, tok.end, replacement)


SHAPES.append(Shape(
    id="nan_infinity",
    category="syntax",
    layer="body",
    recoverable=False,
    description="a numeric field becomes NaN, Infinity, or -Infinity",
    note=(
        "Models trained on Python/NumPy transcripts emit these literals for "
        "missing or overflowed values. The original number is destroyed, so "
        "a robust parser must reject or surface the sentinel explicitly."
    ),
    apply=_apply_nan_infinity,
    applies=lambda ctx: bool(numbers(tokenize(ctx.text))),
))


def _mutate_number_text(txt: str) -> str:
    digits = txt.lstrip("-")
    if digits.isdigit() and len(digits) >= 4:
        # 1234567 -> 1_234_567 (Python numeric-literal habit)
        grouped = ""
        for i, ch in enumerate(reversed(digits)):
            if i and i % 3 == 0:
                grouped = "_" + grouped
            grouped = ch + grouped
        return ("-" if txt.startswith("-") else "") + grouped
    if txt.startswith("0.") and len(txt) > 2:
        return txt[1:]  # 0.5 -> .5
    if not txt.startswith("-"):
        return "+" + txt  # 42 -> +42
    return "-0" + txt[1:]  # -42 -> -042 (leading zero)


def _apply_nonstandard_numbers(ctx: MutationContext) -> str:
    tok = ctx.rng.choice(numbers(tokenize(ctx.text)))
    return splice(ctx.text, tok.start, tok.end, _mutate_number_text(tok.text))


SHAPES.append(Shape(
    id="nonstandard_numbers",
    category="syntax",
    layer="body",
    recoverable=True,
    description="a number written as +42, .5, -042, or 1_000",
    note=(
        "Value-preserving but grammar-violating number spellings copied from "
        "Python source and financial prose. The numeric value survives, so a "
        "lenient parser can recover the payload exactly."
    ),
    apply=_apply_nonstandard_numbers,
    applies=lambda ctx: bool(numbers(tokenize(ctx.text))),
))


def _apply_fullwidth_punct(ctx: MutationContext) -> str:
    mapping = {":": "：", ",": "，"}
    pieces = []
    for tok in tokenize(ctx.text):
        if tok.kind == "punct" and tok.text in mapping:
            pieces.append(mapping[tok.text])
        else:
            pieces.append(tok.text)
    return "".join(pieces)


SHAPES.append(Shape(
    id="fullwidth_punct",
    category="syntax",
    layer="body",
    recoverable=True,
    description="full-width ： and ， replace every structural : and ,",
    note=(
        "A CJK-context failure: models switch to full-width punctuation "
        "mid-generation when the surrounding conversation is Chinese or "
        "Japanese. Visually near-identical, byte-wise fatal."
    ),
    apply=_apply_fullwidth_punct,
    applies=lambda ctx: bool(structural(tokenize(ctx.text), ":,")),
))


# --------------------------------------------------------------------------
# structure category (body layer)
# --------------------------------------------------------------------------

def _apply_ellipsis_item(ctx: MutationContext) -> str:
    spots = _trailing_comma_spots(ctx.text)
    pos = ctx.rng.choice(spots)
    marker = ctx.rng.choice(["...", "…"])
    return splice(ctx.text, pos, pos, ", " + marker)


SHAPES.append(Shape(
    id="ellipsis_item",
    category="structure",
    layer="body",
    recoverable=True,
    description="an '...' placeholder appended as if more items follow",
    note=(
        "The abbreviation reflex: asked for a long list, the model writes a "
        "few items and then literal '...' meaning 'and so on'. Dropping the "
        "placeholder recovers the payload it did emit."
    ),
    apply=_apply_ellipsis_item,
    applies=lambda ctx: bool(_trailing_comma_spots(ctx.text)),
))


def _apply_jsonl_spray(ctx: MutationContext) -> str:
    lines = [json.dumps(item, ensure_ascii=False) for item in ctx.payload]
    return "\n".join(lines)


SHAPES.append(Shape(
    id="jsonl_spray",
    category="structure",
    layer="body",
    recoverable=True,
    description="an array is emitted as one bare object per line (JSONL)",
    note=(
        "Asked for 'a JSON list', the model streams one record per line with "
        "no brackets or commas — valid JSON Lines, invalid JSON. Only "
        "applies when the payload is an array of two or more items."
    ),
    apply=_apply_jsonl_spray,
    applies=lambda ctx: isinstance(ctx.payload, list) and len(ctx.payload) >= 2,
))


def _apply_double_encoded(ctx: MutationContext) -> str:
    compact = json.dumps(ctx.payload, ensure_ascii=False, separators=(", ", ": "))
    return json.dumps(compact, ensure_ascii=False)


SHAPES.append(Shape(
    id="double_encoded",
    category="structure",
    layer="body",
    recoverable=True,
    description="the JSON is serialized twice: a string containing JSON",
    note=(
        "A tool-calling classic: the model (or a middle layer) stringifies "
        "an already-encoded value, so json.loads succeeds — and hands back a "
        "string. Parsers that never check the result type pass it downstream."
    ),
    apply=_apply_double_encoded,
))


def _apply_duplicate_output(ctx: MutationContext) -> str:
    sep = ctx.rng.choice(["\n", "\n\n"])
    return ctx.text + sep + ctx.text


SHAPES.append(Shape(
    id="duplicate_output",
    category="structure",
    layer="body",
    recoverable=True,
    description="the entire JSON document is emitted twice in a row",
    note=(
        "Repetition loops near the end of a generation replay the whole "
        "answer. Two concatenated top-level values are not JSON; the first "
        "balanced value is the payload."
    ),
    apply=_apply_duplicate_output,
))


def _apply_self_correction(ctx: MutationContext) -> str:
    spots = _trailing_comma_spots(ctx.text)
    if spots:
        pos = ctx.rng.choice(spots)
        broken = splice(ctx.text, pos, pos, ",")
    else:
        broken = ctx.text[:-1]
    connector = ctx.rng.choice(_CORRECTIONS)
    return broken + "\n\n" + connector + "\n\n" + ctx.text


SHAPES.append(Shape(
    id="self_correction",
    category="structure",
    layer="body",
    recoverable=True,
    description="a broken first attempt, an apology, then the real JSON",
    note=(
        "Models notice their own syntax error mid-answer and start over in "
        "the same completion. The last complete value is authoritative; "
        "parsers that grab the first one ingest the broken attempt."
    ),
    apply=_apply_self_correction,
))


def _last_closer(text: str):
    tokens = tokenize(text)
    for tok in reversed(tokens):
        if tok.kind == "ws":
            continue
        if tok.kind == "punct" and tok.text in "}]":
            return tok
        return None
    return None


def _apply_unbalanced(ctx: MutationContext) -> str:
    tok = _last_closer(ctx.text)
    return splice(ctx.text, tok.start, tok.end, "").rstrip() if tok else ctx.text


SHAPES.append(Shape(
    id="unbalanced",
    category="structure",
    layer="body",
    recoverable=True,
    description="the final closing brace or bracket never arrives",
    note=(
        "The model considers the answer finished one token early. No data "
        "is lost, so appending the missing closers recovers the payload — "
        "distinguishing this from a mid-value truncation."
    ),
    apply=_apply_unbalanced,
    applies=lambda ctx: _last_closer(ctx.text) is not None,
))


# --------------------------------------------------------------------------
# noise category (body layer)
# --------------------------------------------------------------------------

def _apply_html_escaped(ctx: MutationContext) -> str:
    return (
        ctx.text.replace("&", "&amp;")
        .replace('"', "&quot;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


SHAPES.append(Shape(
    id="html_escaped",
    category="noise",
    layer="body",
    recoverable=True,
    description='every " becomes &quot;, & becomes &amp;, and so on',
    note=(
        "Output that transited an HTML-rendering layer (or a model imitating "
        "scraped web text) arrives entity-escaped end to end."
    ),
    apply=_apply_html_escaped,
    applies=lambda ctx: '"' in ctx.text,
))
