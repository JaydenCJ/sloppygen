"""Exception hierarchy for sloppygen.

Everything raised on purpose by this package derives from ``SloppygenError``
so callers can catch one type at the boundary. Subclasses exist for the
handful of conditions a caller may reasonably want to branch on.
"""

from __future__ import annotations


class SloppygenError(Exception):
    """Base class for all errors raised deliberately by sloppygen."""


class UnknownShapeError(SloppygenError):
    """A shape id was requested that is not in the registry."""

    def __init__(self, shape_id: str, known: "list[str]") -> None:
        self.shape_id = shape_id
        suggestion = _closest(shape_id, known)
        hint = f" (did you mean {suggestion!r}?)" if suggestion else ""
        super().__init__(
            f"unknown shape {shape_id!r}{hint}; run `sloppygen list` for the catalog"
        )


class ShapeNotApplicableError(SloppygenError):
    """A shape cannot corrupt the given payload (e.g. no string values)."""

    def __init__(self, shape_id: str, reason: str) -> None:
        self.shape_id = shape_id
        super().__init__(f"shape {shape_id!r} does not apply: {reason}")


class CompositionError(SloppygenError):
    """An invalid shape stack was requested (e.g. two shapes on one layer)."""


class PayloadError(SloppygenError):
    """The payload source was missing, unreadable, or not valid JSON."""


class CorpusFormatError(SloppygenError):
    """A corpus JSONL file is malformed or missing required fields."""


def _closest(candidate: str, known: "list[str]") -> "str | None":
    """Cheap edit-distance-free suggestion: longest shared prefix wins."""
    best, best_len = None, 2  # require at least a 3-char shared prefix
    for name in known:
        common = 0
        for a, b in zip(candidate, name):
            if a != b:
                break
            common += 1
        if common > best_len:
            best, best_len = name, common
    return best
