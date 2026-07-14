#!/usr/bin/env python3
"""A deliberately naive JSON extractor — the one most codebases start with.

It splits on markdown fences, slices between the first ``{`` and the last
``}``, and calls ``json.loads``. It looks reasonable in review and survives
the happy path; ``sloppygen check`` shows exactly which documented failure
shapes make it crash with a traceback.

Harness contract (see docs/corpus-format.md): sample text arrives on stdin,
the parsed value goes to stdout as JSON, exit 0. Any uncaught exception is
counted as a crash — which is the point of this file.

    sloppygen corpus --seed 42 --count 62 -o corpus.jsonl
    sloppygen check corpus.jsonl --cmd "python3 examples/naive_parser.py"
"""

import json
import sys


def parse(text):
    if "```" in text:
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[len("json"):]
    start = text.index("{")       # ValueError when no object at all
    end = text.rindex("}")        # ValueError when truncation ate the closer
    return json.loads(text[start:end + 1])


if __name__ == "__main__":
    value = parse(sys.stdin.read())
    json.dump(value, sys.stdout)
