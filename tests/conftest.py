"""Shared fixtures: fixed payloads that exercise every shape's preconditions."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Zero runtime dependencies means the package runs straight from src/ with no
# install step; tests import it the same way scripts/smoke.sh runs it.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


@pytest.fixture
def payload():
    """An object payload rich enough for every body shape except jsonl_spray.

    Deliberately fixed (not synthetic) so shape tests can assert on exact
    substrings of the corrupted output.
    """
    return {
        "summary": "The customer can't log in after the password reset was completed.",
        "label": "bug",
        "active": True,
        "parent": None,
        "score": 0.85,
        "count": 1234567,
        "tags": ["urgent", "backend"],
        "owner": {"name": "Ada Lovelace", "office": "Zürich"},
    }


@pytest.fixture
def array_payload():
    """An array payload, required by jsonl_spray."""
    return [
        {"id": 1, "title": "Fix the login flow for existing accounts", "done": False},
        {"id": 2, "title": "Rotate the expired signing certificates", "done": True},
        {"id": 3, "title": "Backfill the missing audit records", "done": False},
    ]
