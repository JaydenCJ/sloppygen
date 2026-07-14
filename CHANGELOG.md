# Changelog

All notable changes to this project are documented in this file. The format is
based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this
project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-07-12

### Added

- 31-shape catalog of documented LLM output failures across four categories:
  `wrapper` (fences, chatter, XML tags, leaked thinking), `syntax` (trailing
  and missing commas, single/smart quotes, unquoted keys, Python literals,
  comments, raw newlines, NaN/Infinity, nonstandard number spellings,
  full-width punctuation), `structure` (ellipsis placeholders, JSONL spray,
  double encoding, duplicated output, self-correction, unbalanced closers,
  truncation mid-token and mid-string), and `noise` (HTML entities,
  zero-width characters, BOM).
- Token-aware mutation engine: body-layer shapes rewrite the canonical JSON
  through a real tokenizer, so a mutation touches exactly the tokens it
  claims to touch and string contents are never corrupted by accident.
- Full determinism: every sample is keyed by SHA-256 over
  `(seed, index, shape ids)`; a corpus is byte-identical across runs and
  platforms, and any sample regenerates from its one-line metadata record.
- Shape stacking (`--stack 2|3`): compose one shape per layer in realistic
  order — body mutation, then wrapper prose, then stream damage.
- `recoverable` flag on every shape and sample, separating "your parser must
  extract this" from "your parser must fail cleanly on this".
- JSONL corpus format with sorted keys and an `expected` payload per sample
  (`docs/corpus-format.md`).
- `check` harness with recovered / rejected / wrong / crash triage, per-shape
  rollup, `--strict` mode, and exit code 1 on findings — for subprocess
  parsers (`--cmd`, stdin/stdout contract) and in-process callables
  (`evaluate`).
- Reference baseline extractor (`sloppygen check --baseline`,
  `sloppygen.extract_json`) documenting exactly which shapes a
  competent-but-plain parser survives — including its pinned known flaw
  (Python's `json.loads` silently accepts `NaN`).
- Seeded synthetic payloads (object and array kinds) that between them give
  every shape something to mutate, plus `--payload` for your own JSON.
- CLI: `list`, `explain` (with live before/after demo), `gen`, `corpus`,
  `check`, `--version`.
- Runnable examples: a deliberately naive parser that `check` catches
  crashing, a Python-API audit script, and a copy-paste pytest regression
  suite.
- 90 offline deterministic tests and `scripts/smoke.sh` (prints `SMOKE OK`).

### Notes

- The repository ships no CI workflow; verification is local —
  `pip install -e '.[dev]' && pytest && bash scripts/smoke.sh`.

[0.1.0]: https://github.com/JaydenCJ/sloppygen/releases/tag/v0.1.0
