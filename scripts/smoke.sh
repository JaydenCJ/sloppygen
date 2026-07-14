#!/usr/bin/env bash
# Smoke test for sloppygen: exercise the real CLI end to end — catalog,
# deterministic generation, corpus emission, and both check harnesses
# (built-in baseline and a subprocess parser that is supposed to crash).
# Self-contained: pure stdlib, no network, idempotent (works from a clean tree).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="${PYTHON:-python3}"
if [ -x "$ROOT/.venv/bin/python" ]; then
  PYTHON="$ROOT/.venv/bin/python"
fi

# Zero runtime dependencies: running from src/ needs no install step.
export PYTHONPATH="$ROOT/src${PYTHONPATH:+:$PYTHONPATH}"

WORKDIR="$(mktemp -d "${TMPDIR:-/tmp}/sloppygen-smoke.XXXXXX")"
trap 'rm -rf "$WORKDIR"' EXIT

fail() { echo "SMOKE FAIL: $1" >&2; exit 1; }

echo "[smoke] python: $("$PYTHON" --version 2>&1)"

# 1. --version agrees with the package version.
version_out="$("$PYTHON" -m sloppygen --version)"
pkg_version="$("$PYTHON" -c 'import sloppygen; print(sloppygen.__version__)')"
[ "$version_out" = "sloppygen $pkg_version" ] \
  || fail "--version mismatch: '$version_out' vs package '$pkg_version'"

# 2. The catalog lists all 31 shapes.
list_out="$("$PYTHON" -m sloppygen list 2>&1)"
echo "$list_out" | grep -q "31 shapes" || fail "list did not report 31 shapes"
echo "$list_out" | grep -q "fence_unclosed" || fail "list missing fence_unclosed"
echo "$list_out" | grep -q "truncated_string" || fail "list missing truncated_string"

# 3. gen is deterministic: the same seed yields byte-identical output.
"$PYTHON" -m sloppygen gen --shape chatter+trailing_comma --seed 7 > "$WORKDIR/a.txt"
"$PYTHON" -m sloppygen gen --shape chatter+trailing_comma --seed 7 > "$WORKDIR/b.txt"
cmp -s "$WORKDIR/a.txt" "$WORKDIR/b.txt" || fail "gen is not deterministic"

# 4. gen corrupts a user-supplied payload.
printf '{"city": "Tokyo", "ok": true}' > "$WORKDIR/payload.json"
gen_out="$("$PYTHON" -m sloppygen gen --shape fence_unclosed --payload "$WORKDIR/payload.json")"
echo "$gen_out" | head -1 | grep -q '^```json' || fail "gen did not open a fence"
echo "$gen_out" | grep -q '"city": "Tokyo"' || fail "gen lost the payload"

# 5. corpus emits the requested JSONL, byte-identically on re-run.
"$PYTHON" -m sloppygen corpus --seed 42 --count 62 -o "$WORKDIR/corpus.jsonl" 2>"$WORKDIR/corpus.log"
grep -q "wrote 62 samples" "$WORKDIR/corpus.log" || fail "corpus summary missing"
[ "$(wc -l < "$WORKDIR/corpus.jsonl")" -eq 62 ] || fail "corpus line count != 62"
"$PYTHON" -m sloppygen corpus --seed 42 --count 62 -o "$WORKDIR/corpus2.jsonl" 2>/dev/null
cmp -s "$WORKDIR/corpus.jsonl" "$WORKDIR/corpus2.jsonl" || fail "corpus is not deterministic"

# 6. check --baseline: no crashes, and the documented nan_infinity flaw is
#    surfaced as a "wrong" finding (exit code 1).
set +e
baseline_out="$("$PYTHON" -m sloppygen check "$WORKDIR/corpus.jsonl" --baseline)"
baseline_rc=$?
set -e
echo "$baseline_out" | tail -3 | sed 's/^/[baseline] /'
[ "$baseline_rc" -eq 1 ] || fail "baseline check should exit 1 (nan finding), got $baseline_rc"
echo "$baseline_out" | grep -Eq "totals +62 " || fail "baseline totals missing"
echo "$baseline_out" | grep -q "0 crash" || fail "baseline must not crash"
echo "$baseline_out" | grep -q "nan_infinity" || fail "nan_infinity finding not surfaced"

# 7. check --cmd: the deliberately naive example parser crashes a lot.
set +e
naive_out="$("$PYTHON" -m sloppygen check "$WORKDIR/corpus.jsonl" \
  --cmd "$PYTHON $ROOT/examples/naive_parser.py")"
naive_rc=$?
set -e
echo "$naive_out" | grep "findings:" | sed 's/^/[naive] /'
[ "$naive_rc" -eq 1 ] || fail "naive check should exit 1, got $naive_rc"
crashes="$(echo "$naive_out" | grep -Eo "[0-9]+ crash" | head -1 | grep -Eo "[0-9]+")"
[ "$crashes" -ge 10 ] || fail "expected >=10 naive crashes, got $crashes"

# 8. A clean wrapper-only corpus passes the baseline with exit 0.
"$PYTHON" -m sloppygen corpus --seed 1 --count 8 --shapes fence,chatter \
  -o "$WORKDIR/clean.jsonl" 2>/dev/null
"$PYTHON" -m sloppygen check "$WORKDIR/clean.jsonl" --baseline >/dev/null \
  || fail "baseline should fully recover fence+chatter samples"

# 9. explain renders a before/after demo.
"$PYTHON" -m sloppygen explain self_correction | grep -q "sloppified (seed 42):" \
  || fail "explain missing the sloppified demo"

echo "SMOKE OK"
