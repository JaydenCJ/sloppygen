# Contributing to sloppygen

Thanks for your interest in contributing. Issues, discussions, and pull
requests are all welcome.

## Development setup

```bash
git clone https://github.com/JaydenCJ/sloppygen
cd sloppygen
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

## Running the checks

```bash
pytest                 # 90 unit + CLI tests, fully offline
bash scripts/smoke.sh  # end-to-end: catalog, gen, corpus, both check harnesses
```

Both must pass before a pull request is reviewed; `scripts/smoke.sh` drives
the real CLI against a temp directory and must print `SMOKE OK`. Everything
runs offline and needs no API keys — there is no network code in this
package, and that is a feature.

## Ground rules

- **No new runtime dependencies.** The core package is standard-library
  only. Test-only dependencies belong in the `dev` extra and need
  justification in the PR.
- **Determinism is the product.** A sample is fully defined by
  `(version, seed, payload, shapes, index)`. Never reorder or edit existing
  shapes in a way that changes their output for the same inputs within a
  minor version — append new shapes at the end of their module's `SHAPES`
  list instead. `tests/test_determinism.py` pins a golden value on purpose.
- **New shapes must be documented failures, not inventions.** Each shape
  needs a `note` explaining why real models produce it, an entry in
  `docs/shapes.md`, an honest `recoverable` flag, and tests proving it
  corrupts (the catalog-wide invariant in `tests/test_engine.py` will hold
  you to it).
- **Body mutations go through the tokenizer.** No blind regex surgery on
  JSON text; use `sloppygen.textops` so mutations touch exactly the tokens
  they claim to touch.
- Code comments and doc comments are written in English.

## Reporting bugs

Please include the output of `sloppygen --version`, the exact command line
or API call, and — for generation bugs — the sample's metadata line from the
corpus (its `seed`, `index`, and `shapes` regenerate the sample exactly, so
a one-line JSON record is a complete repro).

## Security

Please do not report security issues in public GitHub issues. Use GitHub's
private vulnerability reporting on this repository instead.
