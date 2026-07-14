"""Structure-aware text surgery for JSON documents.

sloppygen never mutates JSON with blind regular expressions. Body-layer
shapes operate on the token stream produced by :func:`tokenize`, so a shape
can re-quote exactly the string tokens, or drop exactly one structural comma,
without corrupting anything it did not mean to corrupt.

The tokenizer accepts *valid* JSON text (which is all it ever sees: body
shapes always start from the canonical serialization of the payload).
:func:`scan_balanced` and :func:`string_spans` work on arbitrary text and are
shared with the reference extractor in :mod:`sloppygen.baseline`.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Iterator, List, Tuple

_PUNCT = frozenset("{}[]:,")
_WS = frozenset(" \t\r\n")
_LITERALS = ("true", "false", "null")
_NUMBER_CHARS = frozenset("-+.eE0123456789")


@dataclass
class Token:
    """One lexical unit of a JSON document.

    ``kind`` is one of ``punct``, ``string``, ``number``, ``literal``, ``ws``.
    ``is_key`` is set on string tokens that are immediately followed (modulo
    whitespace) by a colon, i.e. object keys.
    """

    kind: str
    text: str
    start: int
    end: int
    is_key: bool = field(default=False)

    def decoded(self) -> object:
        """Decode a string/number/literal token to its Python value."""
        return json.loads(self.text)


def tokenize(text: str) -> List[Token]:
    """Split valid JSON text into tokens, preserving every byte.

    ``render(tokenize(text)) == text`` holds for any valid JSON document.
    Raises ``ValueError`` on input that is not lexically JSON.
    """
    tokens: List[Token] = []
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if c in _WS:
            j = i
            while j < n and text[j] in _WS:
                j += 1
            tokens.append(Token("ws", text[i:j], i, j))
            i = j
        elif c in _PUNCT:
            tokens.append(Token("punct", c, i, i + 1))
            i += 1
        elif c == '"':
            j = _scan_string(text, i)
            tokens.append(Token("string", text[i:j], i, j))
            i = j
        elif text.startswith(_LITERALS, i):
            for lit in _LITERALS:
                if text.startswith(lit, i):
                    tokens.append(Token("literal", lit, i, i + len(lit)))
                    i += len(lit)
                    break
        else:
            j = i
            while j < n and text[j] in _NUMBER_CHARS:
                j += 1
            if j == i:
                raise ValueError(f"unexpected character {c!r} at offset {i}")
            tokens.append(Token("number", text[i:j], i, j))
            i = j
    _mark_keys(tokens)
    return tokens


def render(tokens: List[Token]) -> str:
    """Reassemble a token list into text."""
    return "".join(tok.text for tok in tokens)


def _scan_string(text: str, start: int) -> int:
    """Return the index one past the closing quote of the string at start."""
    j = start + 1
    n = len(text)
    while j < n:
        if text[j] == "\\":
            j += 2
        elif text[j] == '"':
            return j + 1
        else:
            j += 1
    raise ValueError(f"unterminated string starting at offset {start}")


def _mark_keys(tokens: List[Token]) -> None:
    for idx, tok in enumerate(tokens):
        if tok.kind != "string":
            continue
        k = idx + 1
        while k < len(tokens) and tokens[k].kind == "ws":
            k += 1
        if k < len(tokens) and tokens[k].kind == "punct" and tokens[k].text == ":":
            tok.is_key = True


def strings(tokens: List[Token], keys: "bool | None" = None) -> List[Token]:
    """String tokens, optionally filtered to keys (True) or values (False)."""
    out = []
    for tok in tokens:
        if tok.kind != "string":
            continue
        if keys is not None and tok.is_key is not keys:
            continue
        out.append(tok)
    return out


def numbers(tokens: List[Token]) -> List[Token]:
    return [tok for tok in tokens if tok.kind == "number"]


def structural(tokens: List[Token], chars: str) -> List[Token]:
    """Punctuation tokens whose text is one of ``chars``."""
    wanted = frozenset(chars)
    return [tok for tok in tokens if tok.kind == "punct" and tok.text in wanted]


def splice(text: str, start: int, end: int, replacement: str) -> str:
    """Replace text[start:end] with ``replacement``."""
    return text[:start] + replacement + text[end:]


def container_close_spots(tokens: List[Token]) -> List[int]:
    """Offsets just after the last element of each non-empty object/array.

    These are the exact positions where a trailing comma (or an ellipsis
    placeholder) can be inserted: right before a ``}`` or ``]`` whose
    preceding non-whitespace token is a value, not an opener or a comma.
    """
    spots: List[int] = []
    for i, tok in enumerate(tokens):
        if tok.kind == "punct" and tok.text in "}]":
            j = i - 1
            while j >= 0 and tokens[j].kind == "ws":
                j -= 1
            if j < 0:
                continue
            prev = tokens[j]
            if prev.kind == "punct" and prev.text in "{[,:":
                continue
            spots.append(prev.end)
    return spots


def scan_balanced(text: str, start: int) -> int:
    """Scan one balanced JSON object/array starting at ``start``.

    ``text[start]`` must be ``{`` or ``[``. Returns the index one past the
    matching closer, honouring strings and escapes, or ``-1`` if the value is
    incomplete (truncated / unbalanced input). Works on arbitrary text.
    """
    opener = text[start]
    if opener not in "{[":
        raise ValueError("scan_balanced must start at '{' or '['")
    depth = 0
    in_string = False
    i, n = start, len(text)
    while i < n:
        c = text[i]
        if in_string:
            if c == "\\":
                i += 2
                continue
            if c == '"':
                in_string = False
        elif c == '"':
            in_string = True
        elif c in "{[":
            depth += 1
        elif c in "}]":
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    return -1


def string_spans(text: str) -> List[Tuple[int, int]]:
    """Interior (start, end) spans of double-quoted runs in arbitrary text.

    A best-effort scanner used by stream-layer shapes to find a cut point
    inside *some* quoted region. It honours backslash escapes but makes no
    attempt to understand the surrounding grammar.
    """
    spans: List[Tuple[int, int]] = []
    i, n = 0, len(text)
    while i < n:
        if text[i] == '"':
            j = i + 1
            while j < n:
                if text[j] == "\\":
                    j += 2
                elif text[j] == '"':
                    break
                else:
                    j += 1
            if j < n:
                spans.append((i + 1, j))
                i = j + 1
                continue
            break
        i += 1
    return spans


def iter_lines_with_offsets(text: str) -> Iterator[Tuple[int, str]]:
    """Yield (offset_of_line_start, line_without_newline) pairs."""
    offset = 0
    for line in text.split("\n"):
        yield offset, line
        offset += len(line) + 1
