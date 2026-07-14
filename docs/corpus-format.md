# Corpus format and harness contract

## The JSONL corpus

`sloppygen corpus` emits one JSON object per line, UTF-8, keys sorted. Each
record is self-describing: it carries the corrupted text, the payload a
parser should recover, and enough metadata to regenerate the sample from
scratch.

| Key | Type | Meaning |
|---|---|---|
| `id` | string | `"<index padded to 4>-<shape ids joined by +>"`, e.g. `0007-single_quotes` |
| `shapes` | string[] | shape ids applied, in layer order (body → wrap → stream) |
| `category` | string | category of the primary (first) shape |
| `recoverable` | bool | whether the payload is in principle recoverable from `text` (conjunction over the stack) |
| `seed` | int | the corpus seed |
| `index` | int | the sample index within the seed |
| `text` | string | the corrupted transcript — what your parser receives |
| `expected` | any | the original payload — what it should recover |

Regeneration guarantee: `sloppygen gen --shape <shapes joined by +> --seed
<seed> --index <index>` with the same payload reproduces `text`
byte-for-byte. Every random decision draws from a stream keyed by SHA-256
over `(seed, index, shape ids)`, so streams are independent: changing the
index re-keys the whole stream rather than shifting it.

A corpus is therefore fully defined by `(sloppygen version, seed, payload,
options)`. Commit the command line, not the file — or commit the file and
diff it, both work.

## The `check` harness contract

`sloppygen check <corpus>` runs a parser over every sample and triages each
result into exactly one status:

| Status | Meaning | Finding? |
|---|---|---|
| `recovered` | parser returned a value equal to `expected` | no |
| `rejected` | parser refused cleanly | only with `--strict`, and only when the sample was `recoverable` |
| `wrong` | parser returned a value — the wrong one | **always** (silent bad data is the worst outcome) |
| `crash` | parser blew up | **always** |

`check` exits `1` when findings exist, `0` otherwise, so it slots directly
into CI.

### Subprocess parsers (`--cmd`)

The sample `text` arrives on stdin. Your parser:

- prints the extracted value as JSON on stdout and exits `0`, or
- exits `1` (without a traceback) to reject the sample cleanly.

Everything else is a crash: exit code `1` with a Python traceback on stderr,
any exit code ≥ 2, a signal, a timeout (`--timeout`, default 10 s), or exit
`0` with stdout that is not valid JSON.

### In-process parsers (`evaluate`)

The Python API mirrors the same contract for a callable:

```python
from sloppygen import corpus, evaluate, synthetic_payload

report = evaluate(corpus(synthetic_payload(seed=7), count=62, seed=7), my_parser)
```

- return the parsed value → `recovered` or `wrong`;
- raise `ValueError` (which includes `json.JSONDecodeError`) → `rejected`;
- raise anything else → `crash`.

Comparison is a JSON round-trip with sorted keys, so tuples vs lists and
`3` vs `3.0` normalize before the equality check.
