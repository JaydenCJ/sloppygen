"""Deterministic random-stream derivation.

Every sample sloppygen emits is produced from a ``random.Random`` seeded by
SHA-256 over ``(seed, index, shape ids...)``. Two consequences:

* The same (seed, index, shapes) triple yields byte-identical output on any
  platform and any Python >= 3.9 — ``random.Random`` guarantees a stable
  Mersenne Twister sequence for a given seed.
* Streams are independent: changing the sample index or the shape stack
  re-keys the whole stream instead of shifting it, so inserting a shape into
  the registry never silently perturbs neighbouring samples of an existing
  (seed, index, shapes) request.
"""

from __future__ import annotations

import hashlib
import random

# Separator that cannot appear in a shape id or a decimal index, so that
# derive("a", "bc") and derive("ab", "c") key different streams.
_SEP = "\x1f"

DEFAULT_SEED = 42


def derive_rng(seed: int, *parts: object) -> random.Random:
    """Return a ``random.Random`` keyed by ``seed`` and the given parts."""
    material = _SEP.join([str(int(seed))] + [str(p) for p in parts])
    digest = hashlib.sha256(material.encode("utf-8")).digest()
    return random.Random(int.from_bytes(digest[:8], "big"))
