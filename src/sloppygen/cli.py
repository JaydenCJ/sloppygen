"""The ``sloppygen`` command-line interface.

Subcommands:

* ``list``    — browse the shape catalog
* ``explain`` — one shape in depth, with a before/after demo
* ``gen``     — emit a single corrupted sample
* ``corpus``  — emit a deterministic JSONL corpus
* ``check``   — run a parser (subprocess or the built-in baseline) over a
  corpus and triage crashes, wrong answers, and rejections

Everything runs offline; there is no network code anywhere in this package.
"""

from __future__ import annotations

import argparse
import json
import shlex
import sys
from typing import List, Optional

from . import __version__
from .baseline import extract_json
from .check import evaluate, run_command
from .corpusio import load_corpus, write_jsonl
from .engine import DEFAULT_COUNT, canonicalize, corpus, generate
from .errors import SloppygenError
from .payload import DEMO_ARRAY, DEMO_OBJECT, load_payload, synthetic_payload
from .registry import CATEGORIES, MutationContext, all_shapes, get_shape
from .rng import DEFAULT_SEED, derive_rng


def main(argv: "Optional[List[str]]" = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 2
    try:
        return args.func(args)
    except SloppygenError as exc:
        print(f"sloppygen: error: {exc}", file=sys.stderr)
        return 2
    except BrokenPipeError:
        return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sloppygen",
        description=(
            "Seeded generator of malformed LLM output — broken JSON, stray "
            "fences — to harden parsers."
        ),
    )
    parser.add_argument(
        "--version", action="version", version=f"sloppygen {__version__}"
    )
    sub = parser.add_subparsers(dest="command")
    parser.set_defaults(command=None)

    p_list = sub.add_parser("list", help="list all failure shapes")
    p_list.add_argument("--category", choices=CATEGORIES, help="filter by category")
    p_list.add_argument("--json", action="store_true", help="machine-readable output")
    p_list.set_defaults(func=_cmd_list)

    p_explain = sub.add_parser("explain", help="show one shape with a before/after demo")
    p_explain.add_argument("shape", help="shape id (see `sloppygen list`)")
    p_explain.add_argument("--seed", type=int, default=DEFAULT_SEED)
    p_explain.set_defaults(func=_cmd_explain)

    p_gen = sub.add_parser("gen", help="emit one corrupted sample")
    p_gen.add_argument("--shape", required=True, help="shape id, or a 'body+wrap' stack")
    p_gen.add_argument("--seed", type=int, default=DEFAULT_SEED)
    p_gen.add_argument("--index", type=int, default=0, help="sample index within the seed")
    p_gen.add_argument(
        "--payload",
        help="JSON file to corrupt ('-' for stdin); default: a synthetic payload",
    )
    p_gen.add_argument(
        "--meta", action="store_true", help="print the full JSON record, not just the text"
    )
    p_gen.set_defaults(func=_cmd_gen)

    p_corpus = sub.add_parser("corpus", help="emit a deterministic JSONL corpus")
    p_corpus.add_argument("--seed", type=int, default=DEFAULT_SEED)
    p_corpus.add_argument("--count", type=int, default=DEFAULT_COUNT)
    p_corpus.add_argument("--payload", help="JSON file to corrupt ('-' for stdin)")
    p_corpus.add_argument("--shapes", help="comma-separated shape ids to use")
    p_corpus.add_argument("--category", choices=CATEGORIES, action="append",
                          help="restrict to a category (repeatable)")
    p_corpus.add_argument("--stack", type=int, default=1, choices=(1, 2, 3),
                          help="shapes per sample (body + wrap/stream layers)")
    p_corpus.add_argument("-o", "--output", help="write JSONL here (default: stdout)")
    p_corpus.set_defaults(func=_cmd_corpus)

    p_check = sub.add_parser("check", help="run a parser over a corpus and triage failures")
    p_check.add_argument("corpus", help="corpus JSONL file from `sloppygen corpus`")
    group = p_check.add_mutually_exclusive_group(required=True)
    group.add_argument("--cmd", help="parser command; sample text on stdin, JSON on stdout")
    group.add_argument("--baseline", action="store_true",
                       help="benchmark the built-in reference extractor instead")
    p_check.add_argument("--strict", action="store_true",
                         help="also count clean rejections of recoverable samples as findings")
    p_check.add_argument("--timeout", type=float, default=10.0,
                         help="per-sample timeout for --cmd (seconds)")
    p_check.add_argument("--show", type=int, default=8, help="findings to detail in the report")
    p_check.set_defaults(func=_cmd_check)

    return parser


def _cmd_list(args: argparse.Namespace) -> int:
    shapes = all_shapes(categories=[args.category] if args.category else None)
    if args.json:
        records = [
            {
                "id": s.id,
                "category": s.category,
                "layer": s.layer,
                "recoverable": s.recoverable,
                "description": s.description,
            }
            for s in shapes
        ]
        print(json.dumps(records, indent=2, ensure_ascii=False))
        return 0
    width = max(len(s.id) for s in shapes)
    print(f"{'id':<{width}}  {'category':<9}  {'layer':<6}  {'recov':<5}  description")
    for s in shapes:
        recov = "yes" if s.recoverable else "no"
        print(f"{s.id:<{width}}  {s.category:<9}  {s.layer:<6}  {recov:<5}  {s.description}")
    print(f"\n{len(shapes)} shapes", file=sys.stderr)
    return 0


def _cmd_explain(args: argparse.Namespace) -> int:
    shape = get_shape(args.shape)
    demo_payload = _demo_payload_for(shape)
    print(f"shape: {shape.id}")
    print(f"category: {shape.category}   layer: {shape.layer}   "
          f"recoverable: {'yes' if shape.recoverable else 'no'}")
    print(f"what: {shape.description}")
    print(f"why:  {shape.note}")
    print()
    print("canonical payload:")
    _indented(canonicalize(demo_payload))
    sample = generate(demo_payload, shape, seed=args.seed)
    print()
    print(f"sloppified (seed {args.seed}):")
    _indented(sample.text)
    return 0


def _demo_payload_for(shape) -> object:
    probe_rng = derive_rng(0, "probe")
    for candidate in (DEMO_OBJECT, DEMO_ARRAY):
        ctx = MutationContext(
            payload=candidate,
            text=canonicalize(candidate),
            canonical=canonicalize(candidate),
            rng=probe_rng,
        )
        if shape.applies(ctx):
            return candidate
    return DEMO_OBJECT


def _indented(text: str) -> None:
    for line in text.split("\n"):
        print("  " + line)


def _payload_from(args: argparse.Namespace) -> object:
    if args.payload:
        return load_payload(args.payload)
    return synthetic_payload(seed=args.seed)


def _cmd_gen(args: argparse.Namespace) -> int:
    payload = _payload_from(args)
    sample = generate(payload, args.shape, seed=args.seed, index=args.index)
    if args.meta:
        print(json.dumps(sample.to_record(), ensure_ascii=False, sort_keys=True, indent=2))
    else:
        print(sample.text)
    return 0


def _cmd_corpus(args: argparse.Namespace) -> int:
    payload = _payload_from(args)
    shapes = [s.strip() for s in args.shapes.split(",")] if args.shapes else None
    samples = corpus(
        payload,
        count=args.count,
        seed=args.seed,
        shapes=shapes,
        categories=args.category,
        stack=args.stack,
    )
    distinct = len({s.shapes for s in samples})
    combos = "combination" if distinct == 1 else "combinations"
    if args.output:
        with open(args.output, "w", encoding="utf-8") as fh:
            n = write_jsonl(samples, fh)
        dest = args.output
    else:
        n = write_jsonl(samples, sys.stdout)
        dest = "stdout"
    print(
        f"[corpus] wrote {n} sample{'' if n == 1 else 's'} ({distinct} shape {combos}, "
        f"seed {args.seed}, stack {args.stack}) -> {dest}",
        file=sys.stderr,
    )
    return 0


def _cmd_check(args: argparse.Namespace) -> int:
    samples = load_corpus(args.corpus)
    if args.baseline:
        label = "built-in baseline extractor"
        report = evaluate(samples, extract_json)
    else:
        argv = shlex.split(args.cmd)
        if not argv:
            print("sloppygen: error: --cmd is empty", file=sys.stderr)
            return 2
        label = args.cmd
        report = run_command(argv, samples, timeout=args.timeout)
    print(f"[check] parser: {label}")
    print(f"[check] corpus: {args.corpus} ({len(samples)} samples)")
    print()
    print(report.render(strict=args.strict, show=args.show))
    return 1 if report.findings(strict=args.strict) else 0
