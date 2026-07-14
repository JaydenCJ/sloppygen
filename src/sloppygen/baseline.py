"""A reference extractor: the parser you probably already wrote, done well.

:func:`extract_json` is deliberately *modest*. It strips invisible bytes,
prefers a fenced block when one exists, scans for the first balanced JSON
value, and forgives trailing commas — nothing more. It exists for two
reasons:

* ``sloppygen check --baseline`` gives you an instant benchmark: which
  failure shapes does a competent-but-plain extractor survive, and which
  ones does *your* parser need to beat it on?
* It demonstrates the contract the harness expects: return the parsed
  value, raise ``ValueError`` to reject cleanly, and never raise anything
  else.

It intentionally does **not** repair single quotes, Python literals,
comments, or truncation — that is the gap your production parser fills.
"""

from __future__ import annotations

import json
import re
from typing import Any

from .textops import scan_balanced

_INVISIBLE = ("\u200b", "\u2060", "\ufeff")  # ZWSP, word joiner, BOM
_TRAILING_COMMA = re.compile(r",(\s*[}\]])")
_FENCE_LINE = re.compile(r"^\s*```[^\n]*\n", re.MULTILINE)


def extract_json(text: str) -> Any:
    """Best-effort extraction of one JSON object/array from model output.

    Returns the parsed value, or raises ``ValueError`` when no complete
    JSON value can be located — a *clean rejection* in the vocabulary of
    :mod:`sloppygen.check`.
    """
    cleaned = _strip_noise(text)
    region = _fenced_region(cleaned)
    start = _first_container(region)
    if start < 0:
        raise ValueError("no JSON object or array found in output")
    end = scan_balanced(region, start)
    if end < 0:
        raise ValueError("JSON value is truncated or unbalanced")
    chunk = region[start:end]
    try:
        return json.loads(chunk)
    except ValueError:
        pass
    # One repair everyone agrees on: trailing commas before a closer.
    try:
        return json.loads(_TRAILING_COMMA.sub(r"\1", chunk))
    except ValueError:
        raise ValueError("candidate JSON region does not parse") from None


def _strip_noise(text: str) -> str:
    for ch in _INVISIBLE:
        text = text.replace(ch, "")
    return text.replace("\u00a0", " ")  # NBSP -> plain space


def _fenced_region(text: str) -> str:
    """Content after the first fence line, up to the closing fence if any."""
    match = _FENCE_LINE.search(text)
    if not match:
        return text
    rest = text[match.end():]
    closing = rest.find("```")
    return rest[:closing] if closing >= 0 else rest


def _first_container(text: str) -> int:
    candidates = [i for i in (text.find("{"), text.find("[")) if i >= 0]
    return min(candidates) if candidates else -1
