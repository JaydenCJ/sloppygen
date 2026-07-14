"""CLI behavior end to end, in-process: exit codes, stdout/stderr contracts,
and error handling a script author can rely on."""

from __future__ import annotations

import json

import pytest

from sloppygen import __version__
from sloppygen.cli import main


def run(capsys, *argv):
    code = main(list(argv))
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def test_version_matches_package(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    assert capsys.readouterr().out.strip() == f"sloppygen {__version__}"


def test_no_command_prints_help_and_exits_2(capsys):
    code, out, _err = run(capsys)
    assert code == 2
    assert "usage: sloppygen" in out


def test_list_shows_all_shapes_with_count_on_stderr(capsys):
    code, out, err = run(capsys, "list")
    assert code == 0
    assert "trailing_comma" in out and "invisible_chars" in out
    assert "31 shapes" in err


def test_list_json_and_category_filter(capsys):
    code, out, _err = run(capsys, "list", "--json")
    records = json.loads(out)
    assert code == 0 and len(records) == 31
    assert {"id", "category", "layer", "recoverable", "description"} <= set(records[0])
    _code, out, _err = run(capsys, "list", "--category", "noise")
    assert "html_escaped" in out and "fence_unclosed" not in out


def test_gen_prints_text_or_full_meta_record(capsys):
    code, out, _err = run(capsys, "gen", "--shape", "fence", "--seed", "7")
    assert code == 0
    assert out.startswith("```json\n")
    code, out, _err = run(capsys, "gen", "--shape", "fence", "--meta")
    record = json.loads(out)
    assert code == 0
    assert record["shapes"] == ["fence"] and record["recoverable"] is True


def test_gen_with_payload_file(capsys, tmp_path):
    path = tmp_path / "p.json"
    path.write_text('{"hello": "world"}', encoding="utf-8")
    code, out, _err = run(capsys, "gen", "--shape", "chatter", "--payload", str(path))
    assert code == 0
    assert '"hello": "world"' in out


def test_cli_errors_are_clean_and_exit_2(capsys, tmp_path):
    # Unknown shape: exit 2 plus a typo suggestion.
    code, _out, err = run(capsys, "gen", "--shape", "fence_unclose")
    assert code == 2 and "fence_unclosed" in err
    # Shape that cannot bite this payload: exit 2 with a reason.
    path = tmp_path / "p.json"
    path.write_text('{"a": 1}', encoding="utf-8")
    code, _out, err = run(capsys, "gen", "--shape", "jsonl_spray", "--payload", str(path))
    assert code == 2 and "does not apply" in err
    # Missing corpus file: exit 2, not a traceback.
    code, _out, err = run(capsys, "check", "/nonexistent.jsonl", "--baseline")
    assert code == 2 and "cannot read corpus" in err


def test_corpus_writes_jsonl_file_or_pure_stdout(capsys, tmp_path):
    out_path = tmp_path / "c.jsonl"
    code, out, err = run(capsys, "corpus", "--count", "10", "-o", str(out_path))
    assert code == 0 and out == ""
    assert "wrote 10 samples" in err
    lines = out_path.read_text(encoding="utf-8").strip().split("\n")
    assert len(lines) == 10
    assert all(json.loads(line)["seed"] == 42 for line in lines)
    # Without -o, stdout carries nothing but JSONL (summary goes to stderr).
    code, out, _err = run(capsys, "corpus", "--count", "3")
    assert code == 0
    assert [json.loads(line)["index"] for line in out.strip().split("\n")] == [0, 1, 2]


def test_check_baseline_findings_and_exit_code(capsys, tmp_path):
    out_path = tmp_path / "c.jsonl"
    run(capsys, "corpus", "--count", "31", "-o", str(out_path))
    code, out, _err = run(capsys, "check", str(out_path), "--baseline")
    assert "findings:" in out
    # The baseline is caught by nan_infinity (json.loads accepts NaN), so
    # the default corpus yields findings and exit code 1 — pinned behavior.
    assert code == 1
    assert "nan_infinity" in out


def test_check_clean_subset_exits_zero_and_strict_flips_it(capsys, tmp_path):
    clean = tmp_path / "clean.jsonl"
    run(capsys, "corpus", "--count", "8", "--shapes", "fence,chatter", "-o", str(clean))
    code, out, _err = run(capsys, "check", str(clean), "--baseline")
    assert code == 0 and "findings: 0" in out
    quoted = tmp_path / "quoted.jsonl"
    run(capsys, "corpus", "--count", "4", "--shapes", "single_quotes", "-o", str(quoted))
    assert run(capsys, "check", str(quoted), "--baseline")[0] == 0
    code, out, _err = run(capsys, "check", str(quoted), "--baseline", "--strict")
    assert code == 1 and "rejected-but-recoverable" in out


def test_explain_shows_before_and_after_with_matching_demo(capsys):
    code, out, _err = run(capsys, "explain", "trailing_comma")
    assert code == 0
    assert "canonical payload:" in out and "sloppified (seed 42):" in out and "why:" in out
    # Array-only shapes get an array demo payload automatically.
    code, out, _err = run(capsys, "explain", "jsonl_spray")
    assert code == 0 and '{"id": 1' in out
