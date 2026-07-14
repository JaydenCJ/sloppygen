"""The generation engine: shapes x payload x seed -> deterministic samples.

The pipeline for one sample:

1. The payload is serialized to its canonical form (pretty, 2-space,
   non-ASCII preserved) — the way models actually print JSON.
2. The requested shapes are sorted by layer (body -> wrap -> stream) and
   applied in order, at most one shape per layer. Body shapes rewrite the
   valid JSON text; wrap shapes dress it in prose/fences; stream shapes
   damage the final transcript.
3. Every random decision draws from a stream keyed by
   ``(seed, index, shape ids)``, so a sample is fully reproducible from its
   metadata alone.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from .errors import CompositionError, CorpusFormatError, ShapeNotApplicableError
from .registry import LAYER_ORDER, MutationContext, Shape, all_shapes, get_shape
from .rng import DEFAULT_SEED, derive_rng

DEFAULT_COUNT = 64
MAX_STACK = 3

_RECORD_FIELDS = ("id", "shapes", "category", "recoverable", "seed", "index", "text", "expected")


def canonicalize(payload: Any) -> str:
    """Serialize a payload the way sloppygen's shapes expect to see it."""
    return json.dumps(payload, indent=2, ensure_ascii=False)


@dataclass
class Sample:
    """One corrupted transcript plus everything needed to judge a parser.

    ``text`` is what a parser under test receives; ``expected`` is the
    payload it should recover (when ``recoverable`` is true). ``seed`` and
    ``index`` fully determine ``text``, so a failing sample can be
    regenerated from its metadata line alone.
    """

    id: str
    shapes: Tuple[str, ...]
    category: str
    recoverable: bool
    seed: int
    index: int
    text: str
    expected: Any

    def to_record(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "shapes": list(self.shapes),
            "category": self.category,
            "recoverable": self.recoverable,
            "seed": self.seed,
            "index": self.index,
            "text": self.text,
            "expected": self.expected,
        }

    @classmethod
    def from_record(cls, record: Dict[str, Any]) -> "Sample":
        missing = [f for f in _RECORD_FIELDS if f not in record]
        if missing:
            raise CorpusFormatError(
                f"corpus record is missing "
                f"{'field' if len(missing) == 1 else 'fields'}: {', '.join(missing)}"
            )
        return cls(
            id=record["id"],
            shapes=tuple(record["shapes"]),
            category=record["category"],
            recoverable=bool(record["recoverable"]),
            seed=int(record["seed"]),
            index=int(record["index"]),
            text=record["text"],
            expected=record["expected"],
        )


def resolve_shapes(spec: "str | Shape | Sequence[str] | Sequence[Shape]") -> List[Shape]:
    """Normalize a shape spec ('a', 'a+b', ['a', 'b'], Shape) to Shape objects."""
    if isinstance(spec, Shape):
        return [spec]
    if isinstance(spec, str):
        parts = [p.strip() for p in spec.split("+") if p.strip()]
        return [get_shape(p) for p in parts]
    return [s if isinstance(s, Shape) else get_shape(s) for s in spec]


def _validate_stack(shapes: List[Shape]) -> List[Shape]:
    if not shapes:
        raise CompositionError("a sample needs at least one shape")
    if len(shapes) > MAX_STACK:
        raise CompositionError(f"at most {MAX_STACK} shapes per sample, got {len(shapes)}")
    seen: Dict[str, str] = {}
    for shape in shapes:
        if shape.layer in seen:
            raise CompositionError(
                f"shapes {seen[shape.layer]!r} and {shape.id!r} both target the "
                f"{shape.layer} layer; stack at most one shape per layer"
            )
        seen[shape.layer] = shape.id
    return sorted(shapes, key=lambda s: LAYER_ORDER[s.layer])


def generate(
    payload: Any,
    shape: "str | Shape | Sequence[str]",
    seed: int = DEFAULT_SEED,
    index: int = 0,
) -> Sample:
    """Corrupt ``payload`` with one shape (or a '+'-joined stack of shapes).

    Deterministic: the same (payload, shape, seed, index) always returns the
    same sample. Raises :class:`ShapeNotApplicableError` when a shape has
    nothing to bite on (e.g. ``jsonl_spray`` on a non-array payload).
    """
    shapes = _validate_stack(resolve_shapes(shape))
    rng = derive_rng(seed, index, *[s.id for s in shapes])
    canonical = canonicalize(payload)
    text = canonical
    for s in shapes:
        ctx = MutationContext(payload=payload, text=text, canonical=canonical, rng=rng)
        if not s.applies(ctx):
            raise ShapeNotApplicableError(s.id, _why_not(s, payload))
        text = s.apply(ctx)
    ids = tuple(s.id for s in shapes)
    return Sample(
        id=f"{index:04d}-{'+'.join(ids)}",
        shapes=ids,
        category=shapes[0].category,
        recoverable=all(s.recoverable for s in shapes),
        seed=seed,
        index=index,
        text=text,
        expected=payload,
    )


def _why_not(shape: Shape, payload: Any) -> str:
    kind = type(payload).__name__
    return (
        f"the payload (a {kind}) lacks the construct this shape mutates; "
        "try a payload with the relevant strings/numbers/containers"
    )


def applicable_shapes(
    payload: Any,
    shapes: "Optional[Iterable[Shape]]" = None,
) -> List[Shape]:
    """Filter shapes to those whose ``applies`` accepts this payload.

    Applicability is checked against the canonical serialization with an
    inert rng, mirroring what each shape will see at body time.
    """
    canonical = canonicalize(payload)
    probe = MutationContext(
        payload=payload, text=canonical, canonical=canonical, rng=_InertRng()
    )
    pool = list(shapes) if shapes is not None else all_shapes()
    return [s for s in pool if s.applies(probe)]


class _InertRng:
    """A stand-in rng that fails loudly if an ``applies`` predicate draws from it."""

    def __getattr__(self, name: str):  # pragma: no cover - defensive
        raise RuntimeError("applies() predicates must not consume randomness")


def corpus(
    payload: Any,
    count: int = DEFAULT_COUNT,
    seed: int = DEFAULT_SEED,
    shapes: "Optional[Sequence[str]]" = None,
    categories: "Optional[Sequence[str]]" = None,
    stack: int = 1,
) -> List[Sample]:
    """Build a deterministic corpus of ``count`` corrupted samples.

    Shapes are cycled in registry order so every applicable shape appears
    before any shape repeats; extra passes re-key the rng via the sample
    index and produce fresh variants (different chatter, cut points, ...).

    With ``stack=2`` each sample combines a body-layer shape with a
    wrap/stream-layer shape; ``stack=3`` adds a third layer when possible.
    """
    if count < 1:
        raise CompositionError("count must be >= 1")
    if not 1 <= stack <= MAX_STACK:
        raise CompositionError(f"stack must be between 1 and {MAX_STACK}")
    selected = all_shapes(categories=list(categories) if categories else None)
    if shapes:
        wanted = [get_shape(s) for s in shapes]
        selected = [s for s in selected if s in wanted] if categories else wanted
    pool = applicable_shapes(payload, selected)
    if not pool:
        raise ShapeNotApplicableError(
            "corpus", "no selected shape applies to this payload"
        )

    samples: List[Sample] = []
    if stack == 1:
        for i in range(count):
            shape = pool[i % len(pool)]
            samples.append(generate(payload, shape, seed=seed, index=i))
        return samples

    bodies = [s for s in pool if s.layer == "body"]
    wraps = [s for s in pool if s.layer == "wrap"]
    streams = [s for s in pool if s.layer == "stream"]
    others = wraps + streams
    if not bodies or not others:
        raise CompositionError(
            "stacked corpora need at least one applicable body shape and one "
            "wrap/stream shape; loosen the shape/category filter"
        )
    for i in range(count):
        # A later-layer shape may stop applying once the body mutation has
        # rewritten the text (e.g. smart_quotes leaves no straight quote for
        # truncated_string to cut). Resolve deterministically by advancing to
        # the next partner shape.
        for attempt in range(len(others) + 1):
            if stack == 3 and wraps and streams:
                combo: List[Shape] = [
                    bodies[i % len(bodies)],
                    wraps[(i + attempt) % len(wraps)],
                    streams[(i + attempt) % len(streams)],
                ]
            else:
                combo = [bodies[i % len(bodies)], others[(i + attempt) % len(others)]]
            try:
                samples.append(generate(payload, combo, seed=seed, index=i))
                break
            except ShapeNotApplicableError:
                if attempt == len(others):
                    raise
    return samples
