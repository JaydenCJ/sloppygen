"""Payload sources: user-supplied JSON files or seeded synthetic payloads.

The synthetic payloads imitate what LLM apps actually parse — extraction
results, classifications, task lists — and are constructed so that every
body shape has something to bite on: apostrophes for the quote shapes, long
sentences for the newline shape, big integers for the underscore spelling,
booleans, nulls, nested containers, and non-ASCII text.
"""

from __future__ import annotations

import json
import sys
from typing import Any

from .errors import PayloadError
from .rng import DEFAULT_SEED, derive_rng

_NAMES = ("Ada Lovelace", "Grace Hopper", "Alan Turing", "Katherine Johnson", "Edsger Dijkstra")
_CITIES = ("Tokyo", "Zürich", "São Paulo", "Reykjavík", "Nairobi")
_TAGS = ("urgent", "backend", "customer", "billing", "follow-up", "réunion", "設計")
_SENTENCES = (
    "The customer can't log in after the password reset was completed.",
    "Ship the quarterly report before Friday's leadership review meeting.",
    "The API returns stale data when the cache isn't invalidated on write.",
    "Migrate the billing exports so the finance team isn't blocked anymore.",
)
_LABELS = ("bug", "feature_request", "question", "complaint")


def synthetic_payload(seed: int = DEFAULT_SEED, kind: str = "object") -> Any:
    """Build a deterministic, realistic payload for the given seed.

    ``kind='object'`` returns a task-extraction style document (the default);
    ``kind='array'`` returns a list of records, which additionally enables
    array-only shapes such as ``jsonl_spray``.
    """
    if kind not in ("object", "array"):
        raise PayloadError(f"unknown synthetic payload kind {kind!r}")
    rng = derive_rng(seed, "payload", kind)
    if kind == "array":
        return [_record(rng, i) for i in range(rng.randrange(3, 6))]

    tasks = [_record(rng, i) for i in range(rng.randrange(2, 4))]
    return {
        "summary": rng.choice(_SENTENCES),
        "label": rng.choice(_LABELS),
        "confidence": round(rng.uniform(0.5, 0.99), 2),
        "reviewer": rng.choice(_NAMES),
        "office": rng.choice(_CITIES),
        "word_budget": rng.randrange(2000, 90000),
        "escalated": rng.choice([True, False]),
        "parent_id": None,
        "tasks": tasks,
    }


def _record(rng: Any, index: int) -> dict:
    return {
        "id": index + 1,
        "title": rng.choice(_SENTENCES),
        "owner": rng.choice(_NAMES),
        "tags": rng.sample(list(_TAGS), 2),
        "estimate_hours": round(rng.uniform(0.5, 40.0), 1),
        "done": rng.choice([True, False]),
    }


def load_payload(source: str) -> Any:
    """Load a JSON payload from a file path, or from stdin when ``-``."""
    try:
        if source == "-":
            raw = sys.stdin.read()
        else:
            with open(source, "r", encoding="utf-8") as fh:
                raw = fh.read()
    except OSError as exc:
        raise PayloadError(f"cannot read payload from {source!r}: {exc}") from exc
    try:
        return json.loads(raw)
    except ValueError as exc:
        raise PayloadError(
            f"payload from {source!r} is not valid JSON: {exc}. sloppygen "
            "corrupts *valid* payloads; feed it what your app expects on a good day"
        ) from exc


DEMO_OBJECT = {
    "name": "Ada Lovelace",
    "role": "analyst",
    "active": True,
    "score": 0.97,
    "tags": ["math", "pioneer"],
    "note": "Wrote the first published algorithm for a machine.",
}

DEMO_ARRAY = [
    {"id": 1, "city": "Tokyo", "open": True},
    {"id": 2, "city": "Zürich", "open": False},
    {"id": 3, "city": "Nairobi", "open": True},
]
