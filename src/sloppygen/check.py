"""The harness: run a parser over a corpus and triage what happened.

Each sample lands in exactly one status:

===========  ================================================================
status       meaning
===========  ================================================================
recovered    the parser returned a value equal to the expected payload
wrong        the parser returned a value — the *wrong* one (worst outcome:
             no error, bad data flows downstream)
rejected     the parser refused cleanly (``ValueError`` in-process, or exit
             code 1 without a traceback for subprocess parsers)
crash        the parser blew up: any other exception, a traceback on stderr,
             exit codes >= 2, signals, timeouts, or non-JSON stdout
===========  ================================================================

Findings — what makes ``sloppygen check`` exit non-zero — are every crash
and every wrong answer. With ``--strict``, clean rejections of *recoverable*
samples count too, for teams whose parser is supposed to repair, not refuse.
"""

from __future__ import annotations

import json
import subprocess
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Sequence

from .engine import Sample

STATUSES = ("recovered", "rejected", "wrong", "crash")

_TRACEBACK_MARK = "Traceback (most recent call last)"


@dataclass
class Result:
    """The verdict for one sample."""

    sample_id: str
    shapes: "tuple[str, ...]"
    recoverable: bool
    status: str
    detail: str = ""


@dataclass
class Report:
    """All verdicts for one run, with rollups and a text rendering."""

    results: List[Result]

    def counts(self) -> Dict[str, int]:
        out = {status: 0 for status in STATUSES}
        for r in self.results:
            out[r.status] += 1
        return out

    def by_shape(self) -> "OrderedDict[str, Dict[str, int]]":
        rollup: "OrderedDict[str, Dict[str, int]]" = OrderedDict()
        for r in self.results:
            key = "+".join(r.shapes)
            row = rollup.setdefault(key, {status: 0 for status in STATUSES})
            row[r.status] += 1
        return rollup

    def findings(self, strict: bool = False) -> List[Result]:
        out = []
        for r in self.results:
            if r.status in ("crash", "wrong"):
                out.append(r)
            elif strict and r.status == "rejected" and r.recoverable:
                out.append(r)
        return out

    def render(self, strict: bool = False, show: int = 8) -> str:
        rollup = self.by_shape()
        width = max([len("shape")] + [len(k) for k in rollup])
        lines = []
        header = f"{'shape':<{width}}  {'n':>3}  {'recovered':>9}  {'rejected':>8}  {'wrong':>5}  {'crash':>5}"
        lines.append(header)
        for key, row in rollup.items():
            n = sum(row.values())
            lines.append(
                f"{key:<{width}}  {n:>3}  {row['recovered']:>9}  "
                f"{row['rejected']:>8}  {row['wrong']:>5}  {row['crash']:>5}"
            )
        totals = self.counts()
        lines.append(
            f"{'totals':<{width}}  {len(self.results):>3}  {totals['recovered']:>9}  "
            f"{totals['rejected']:>8}  {totals['wrong']:>5}  {totals['crash']:>5}"
        )
        findings = self.findings(strict=strict)
        crash_n = sum(1 for f in findings if f.status == "crash")
        wrong_n = sum(1 for f in findings if f.status == "wrong")
        reject_n = len(findings) - crash_n - wrong_n
        parts = [f"{crash_n} crash", f"{wrong_n} wrong"]
        if strict:
            parts.append(f"{reject_n} rejected-but-recoverable")
        lines.append("")
        lines.append(f"findings: {len(findings)} ({', '.join(parts)})")
        for f in findings[:show]:
            detail = f.detail.strip().splitlines()
            summary = detail[-1] if detail else ""
            lines.append(f"  {f.status:<6} {f.sample_id}  {summary[:100]}")
        if len(findings) > show:
            lines.append(f"  ... and {len(findings) - show} more")
        return "\n".join(lines)


def evaluate(samples: Sequence[Sample], parser: Callable[[str], Any]) -> Report:
    """Run an in-process parser over the corpus.

    Contract: the parser returns the extracted value, raises ``ValueError``
    (which includes ``json.JSONDecodeError``) to reject a sample cleanly,
    and any other exception counts as a crash.
    """
    results = []
    for sample in samples:
        try:
            value = parser(sample.text)
        except ValueError as exc:
            results.append(_result(sample, "rejected", f"{type(exc).__name__}: {exc}"))
        except Exception as exc:  # noqa: BLE001 - crashes are the product here
            results.append(_result(sample, "crash", f"{type(exc).__name__}: {exc}"))
        else:
            status = "recovered" if _json_equal(value, sample.expected) else "wrong"
            detail = "" if status == "recovered" else f"parser returned {_shorten(value)}"
            results.append(_result(sample, status, detail))
    return Report(results)


def run_command(
    argv: Sequence[str],
    samples: Sequence[Sample],
    timeout: float = 10.0,
) -> Report:
    """Run a subprocess parser over the corpus.

    Contract: the sample text arrives on stdin; the parser prints the
    extracted value as JSON on stdout and exits 0, or exits 1 to reject.
    Exit code 1 with a Python traceback on stderr, any exit code >= 2,
    a signal, a timeout, or non-JSON stdout all count as crashes.
    """
    results = []
    for sample in samples:
        try:
            proc = subprocess.run(
                list(argv),
                input=sample.text.encode("utf-8"),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            results.append(_result(sample, "crash", f"timeout after {timeout}s"))
            continue
        stderr = proc.stderr.decode("utf-8", "replace")
        if proc.returncode == 0:
            try:
                value = json.loads(proc.stdout.decode("utf-8", "replace"))
            except ValueError:
                results.append(_result(sample, "crash", "exit 0 but stdout was not JSON"))
                continue
            status = "recovered" if _json_equal(value, sample.expected) else "wrong"
            detail = "" if status == "recovered" else f"parser returned {_shorten(value)}"
            results.append(_result(sample, status, detail))
        elif proc.returncode == 1 and _TRACEBACK_MARK not in stderr:
            results.append(_result(sample, "rejected", stderr))
        else:
            results.append(_result(sample, "crash", stderr or f"exit code {proc.returncode}"))
    return Report(results)


def _result(sample: Sample, status: str, detail: str) -> Result:
    return Result(
        sample_id=sample.id,
        shapes=sample.shapes,
        recoverable=sample.recoverable,
        status=status,
        detail=detail,
    )


def _json_equal(value: Any, expected: Any) -> bool:
    """Compare through a JSON round-trip so tuples/ints/floats normalize."""
    try:
        normalized = json.loads(json.dumps(value, sort_keys=True))
    except (TypeError, ValueError):
        return False
    return normalized == json.loads(json.dumps(expected, sort_keys=True))


def _shorten(value: Any, limit: int = 80) -> str:
    try:
        text = json.dumps(value, ensure_ascii=False)
    except (TypeError, ValueError):
        text = repr(value)
    return text if len(text) <= limit else text[: limit - 3] + "..."
