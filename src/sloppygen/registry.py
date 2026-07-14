"""The shape registry.

A *shape* is one documented way real LLMs mangle structured output. Each
shape declares:

* ``category`` — how users browse the catalog (``wrapper``, ``syntax``,
  ``structure``, ``noise``);
* ``layer`` — where in the pipeline it applies. ``body`` shapes rewrite the
  canonical JSON text (token-aware), ``wrap`` shapes add text around it, and
  ``stream`` shapes do byte-level damage to the final transcript. Shape
  stacks compose in that order, mirroring how a real completion is built:
  the model mangles the JSON, dresses it in prose/fences, and then the
  transport truncates or pollutes the result;
* ``recoverable`` — whether the original payload is in principle mechanically
  recoverable from the corrupted text. Unrecoverable shapes exist to prove a
  parser fails *cleanly*; recoverable ones to prove it can still extract the
  payload;
* ``note`` — one or two sentences on why real models produce this shape.

Registry order is part of the determinism contract: a corpus is defined by
(package version, seed, payload, options). New shapes are appended, never
inserted, within a minor version line.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from .errors import UnknownShapeError

CATEGORIES = ("wrapper", "syntax", "structure", "noise")
LAYERS = ("body", "wrap", "stream")
LAYER_ORDER = {"body": 0, "wrap": 1, "stream": 2}


@dataclass
class MutationContext:
    """Everything a shape sees when it runs.

    ``text`` is the text at the current layer (for body shapes this is the
    canonical serialization and is guaranteed to be valid JSON). ``payload``
    and ``canonical`` never change across the stack. ``rng`` is the derived
    per-sample random stream; ``applies`` predicates must not consume it.
    """

    payload: Any
    text: str
    canonical: str
    rng: Any


def _always(_ctx: MutationContext) -> bool:
    return True


@dataclass(frozen=True)
class Shape:
    """A single documented failure shape."""

    id: str
    category: str
    layer: str
    recoverable: bool
    description: str
    note: str
    apply: Callable[[MutationContext], str]
    applies: Callable[[MutationContext], bool] = field(default=_always)

    def __post_init__(self) -> None:
        if self.category not in CATEGORIES:
            raise ValueError(f"bad category {self.category!r} for shape {self.id!r}")
        if self.layer not in LAYERS:
            raise ValueError(f"bad layer {self.layer!r} for shape {self.id!r}")


_REGISTRY: "Dict[str, Shape]" = {}
_ORDER: "List[str]" = []


def register(shape: Shape) -> Shape:
    """Add a shape to the registry (module import time only)."""
    if shape.id in _REGISTRY:
        raise ValueError(f"duplicate shape id {shape.id!r}")
    _REGISTRY[shape.id] = shape
    _ORDER.append(shape.id)
    return shape


def get_shape(shape_id: str) -> Shape:
    """Look up one shape by id, with a typo suggestion on failure."""
    _ensure_loaded()
    try:
        return _REGISTRY[shape_id]
    except KeyError:
        raise UnknownShapeError(shape_id, _ORDER) from None


def all_shapes(
    categories: "Optional[List[str]]" = None,
    layers: "Optional[List[str]]" = None,
) -> List[Shape]:
    """All shapes in registry order, optionally filtered."""
    _ensure_loaded()
    out = []
    for shape_id in _ORDER:
        shape = _REGISTRY[shape_id]
        if categories and shape.category not in categories:
            continue
        if layers and shape.layer not in layers:
            continue
        out.append(shape)
    return out


def shape_ids() -> List[str]:
    _ensure_loaded()
    return list(_ORDER)


def _ensure_loaded() -> None:
    """Assemble the registry from the shape modules, in canonical order.

    Each module declares a ``SHAPES`` list with no import-time side effects;
    the ordering below — body mutations, then wrappers, then stream damage —
    is the one determinism contract this function owns, and it holds no
    matter which module a caller happens to import first.
    """
    if _ORDER:
        return
    from . import shapes_body, shapes_stream, shapes_wrap

    for module in (shapes_body, shapes_wrap, shapes_stream):
        for shape in module.SHAPES:
            register(shape)
    assert _ORDER, "shape modules declared nothing"
