"""The harness contract, both in-process and subprocess:
recovered / rejected / wrong / crash triage, findings, and exit semantics."""

from __future__ import annotations

import sys
import textwrap

import pytest

from sloppygen import corpus, evaluate, extract_json, generate
from sloppygen.check import run_command


@pytest.fixture
def samples(payload):
    return corpus(payload, count=12, seed=42)


def test_evaluate_triages_recovered_rejected_and_wrong(payload, samples):
    fenced = [generate(payload, "fence", seed=1)]
    assert evaluate(fenced, extract_json).results[0].status == "recovered"

    def refusenik(_text):
        raise ValueError("nope")

    report = evaluate(samples, refusenik)
    assert all(r.status == "rejected" for r in report.results)
    assert report.findings() == []  # clean rejections are not findings

    report = evaluate(fenced, lambda _t: {"totally": "different"})
    assert report.results[0].status == "wrong"
    assert len(report.findings()) == 1  # silent bad data always is


def test_evaluate_non_valueerror_exceptions_are_crashes(samples):
    def fragile(text):
        return text.split("```")[3]  # IndexError on most samples

    report = evaluate(samples, fragile)
    counts = report.counts()
    assert counts["crash"] > 0
    assert sum(counts.values()) == len(samples)  # statuses are exhaustive


def test_strict_counts_rejections_of_recoverable_samples(payload):
    def refusenik(_text):
        raise ValueError("nope")

    recoverable = generate(payload, "fence", seed=1)
    lost_cause = generate(payload, "truncated", seed=1)
    report = evaluate([recoverable, lost_cause], refusenik)
    assert report.findings(strict=False) == []
    # Only the recoverable rejection counts; rejecting a truncation is right.
    assert [f.sample_id for f in report.findings(strict=True)] == [recoverable.id]


def test_report_render_has_rollup_totals_and_truncated_findings(payload):
    report = evaluate(corpus(payload, count=10, seed=1), lambda _t: 0)
    text = report.render(show=2)
    assert "shape" in text and "totals" in text and "findings:" in text
    assert "... and 8 more" in text


def _parser_script(tmp_path, body):
    path = tmp_path / "parser.py"
    path.write_text(textwrap.dedent(body), encoding="utf-8")
    return [sys.executable, str(path)]


def test_run_command_recovered_and_traceback_crash(tmp_path, payload):
    argv = _parser_script(
        tmp_path,
        """
        import json, sys
        text = sys.stdin.read()
        start = text.index("{")
        end = text.rindex("}")
        json.dump(json.loads(text[start:end + 1]), sys.stdout)
        """,
    )
    fine = generate(payload, "chatter", seed=1)
    fatal = generate(payload, "truncated", seed=1)
    report = run_command(argv, [fine, fatal])
    by_id = {r.sample_id: r.status for r in report.results}
    assert by_id[fine.id] == "recovered"
    assert by_id[fatal.id] == "crash"  # uncaught ValueError -> traceback


def test_run_command_exit_1_without_traceback_is_rejection(tmp_path, payload):
    argv = _parser_script(
        tmp_path,
        """
        import sys
        sys.stderr.write("cannot parse this input\\n")
        sys.exit(1)
        """,
    )
    report = run_command(argv, [generate(payload, "fence", seed=1)])
    assert report.results[0].status == "rejected"
    assert "cannot parse" in report.results[0].detail


def test_run_command_contract_violations_are_crashes(tmp_path, payload):
    sample = generate(payload, "fence", seed=1)
    exit2 = run_command(_parser_script(tmp_path, "import sys; sys.exit(2)"), [sample])
    assert exit2.results[0].status == "crash"
    prose = run_command(_parser_script(tmp_path, "print('parsed it, trust me')"), [sample])
    assert prose.results[0].status == "crash"
    assert "not JSON" in prose.results[0].detail


def test_run_command_wrong_answer(tmp_path, payload):
    argv = _parser_script(tmp_path, "print('{}')")
    report = run_command(argv, [generate(payload, "fence", seed=1)])
    assert report.results[0].status == "wrong"
