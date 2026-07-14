#!/usr/bin/env python3
"""Audit a parser with the Python API — no files, no subprocesses.

This drives the same harness `sloppygen check` uses, in process, against the
built-in reference extractor. Swap ``extract_json`` for your own function to
audit your parser: return the parsed value, raise ``ValueError`` to reject a
sample cleanly; anything else you raise is counted as a crash.

    python3 examples/audit_baseline.py
"""

from sloppygen import corpus, evaluate, extract_json, synthetic_payload

payload = synthetic_payload(seed=7)
samples = corpus(payload, count=62, seed=7)

report = evaluate(samples, extract_json)
print(report.render(show=4))

findings = report.findings()
print()
if findings:
    n = len(findings)
    print(f"{n} finding{'' if n == 1 else 's'}: this parser needs work before production.")
raise SystemExit(1 if findings else 0)
