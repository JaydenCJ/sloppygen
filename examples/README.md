# sloppygen examples

Three runnable entry points, all offline and deterministic:

| File | What it shows |
|---|---|
| [`naive_parser.py`](naive_parser.py) | The extractor most codebases start with — and how `sloppygen check --cmd` catches it crashing on 40+ of 62 samples |
| [`audit_baseline.py`](audit_baseline.py) | The Python API: build a corpus in memory, run `evaluate()` against a parser function, render the triage report |
| [`pytest_regression.py`](pytest_regression.py) | A copy-paste pytest suite that turns the whole shape catalog into permanent regression tests for *your* extractor |

Run them from the repository root (no install needed — the package has zero
runtime dependencies):

```bash
export PYTHONPATH=src

# 1. Watch a naive parser get destroyed.
python3 -m sloppygen corpus --seed 42 --count 62 -o /tmp/corpus.jsonl
python3 -m sloppygen check /tmp/corpus.jsonl --cmd "python3 examples/naive_parser.py"

# 2. Audit the built-in baseline via the API.
python3 examples/audit_baseline.py

# 3. Use the catalog as a pytest regression suite.
python3 -m pytest examples/pytest_regression.py
```

The exit code of `check` (and of both example scripts) is `1` when findings
exist, so any of these slots directly into a CI job or a pre-commit hook.
