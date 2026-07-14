"""Corpus serialization: one JSON object per line, sorted keys, UTF-8.

The JSONL format is the interchange point between ``sloppygen corpus`` and
``sloppygen check`` — and between sloppygen and any other tool: each line
carries the corrupted ``text``, the ``expected`` payload, and the metadata
needed to regenerate or triage the sample. See docs/corpus-format.md.
"""

from __future__ import annotations

import json
from typing import IO, Iterable, List

from .engine import Sample
from .errors import CorpusFormatError


def write_jsonl(samples: Iterable[Sample], fh: IO[str]) -> int:
    """Write samples as JSONL. Returns the number of lines written."""
    n = 0
    for sample in samples:
        fh.write(json.dumps(sample.to_record(), ensure_ascii=False, sort_keys=True))
        fh.write("\n")
        n += 1
    return n


def read_jsonl(fh: IO[str], source: str = "<corpus>") -> List[Sample]:
    """Parse a corpus JSONL stream back into samples, validating each line."""
    samples: List[Sample] = []
    for lineno, line in enumerate(fh, start=1):
        line = line.strip("\n")
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except ValueError as exc:
            raise CorpusFormatError(
                f"{source}:{lineno}: line is not valid JSON: {exc}"
            ) from exc
        if not isinstance(record, dict):
            raise CorpusFormatError(
                f"{source}:{lineno}: expected a JSON object, got {type(record).__name__}"
            )
        try:
            samples.append(Sample.from_record(record))
        except CorpusFormatError as exc:
            raise CorpusFormatError(f"{source}:{lineno}: {exc}") from exc
    if not samples:
        raise CorpusFormatError(f"{source}: corpus is empty")
    return samples


def load_corpus(path: str) -> List[Sample]:
    """Read a corpus from a JSONL file on disk."""
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return read_jsonl(fh, source=path)
    except OSError as exc:
        raise CorpusFormatError(f"cannot read corpus {path!r}: {exc}") from exc
