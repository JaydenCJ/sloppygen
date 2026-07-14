"""sloppygen — seeded generator of malformed LLM output to harden parsers.

Public API:

* :func:`generate` / :func:`corpus` — produce corrupted samples from a
  payload, deterministically, offline.
* :func:`shapes` / :func:`get_shape` — browse the failure-shape catalog.
* :func:`synthetic_payload` — seeded realistic payloads when you have none.
* :func:`evaluate` — run an in-process parser over samples and triage
  crashes, wrong answers, and clean rejections.
* :func:`extract_json` — the reference baseline extractor.

Quick taste::

    import sloppygen

    sample = sloppygen.generate({"ok": True}, "chatter+trailing_comma", seed=7)
    my_parser(sample.text)  # does this crash? sloppygen thinks it might
"""

from __future__ import annotations

from .baseline import extract_json
from .check import Report, Result, evaluate, run_command
from .engine import Sample, canonicalize, corpus, generate
from .errors import (
    CompositionError,
    CorpusFormatError,
    PayloadError,
    ShapeNotApplicableError,
    SloppygenError,
    UnknownShapeError,
)
from .payload import load_payload, synthetic_payload
from .registry import Shape, all_shapes as shapes, get_shape

__version__ = "0.1.0"

__all__ = [
    "__version__",
    "generate",
    "corpus",
    "canonicalize",
    "Sample",
    "Shape",
    "shapes",
    "get_shape",
    "synthetic_payload",
    "load_payload",
    "evaluate",
    "run_command",
    "Report",
    "Result",
    "extract_json",
    "SloppygenError",
    "UnknownShapeError",
    "ShapeNotApplicableError",
    "CompositionError",
    "PayloadError",
    "CorpusFormatError",
]
