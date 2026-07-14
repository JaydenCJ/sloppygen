# The shape catalog

A *shape* is one documented way real LLMs mangle structured output. sloppygen
0.1.0 ships 31 of them. This page is the reference; `sloppygen explain <id>`
prints the same information plus a live before/after demo.

## How shapes are organized

Every shape has three orthogonal attributes:

- **category** — how you browse and filter: `wrapper` (noise around intact
  JSON), `syntax` (grammar violations inside the JSON), `structure` (the
  document's overall form is wrong), `noise` (byte-level pollution).
- **layer** — where it applies in the generation pipeline. `body` shapes
  rewrite the canonical JSON text through a tokenizer (never a blind regex);
  `wrap` shapes add text around it; `stream` shapes damage the final
  transcript. Stacked samples compose body → wrap → stream, mirroring how a
  real completion is built and then mangled in transit.
- **recoverable** — whether the original payload is in principle mechanically
  recoverable from the corrupted text. Recoverable shapes test that your
  parser *can* extract the payload; unrecoverable ones (`nan_infinity`,
  `truncated`, `truncated_string`) test that it fails *cleanly* — no crash,
  no silent partial data.

## Catalog

| id | category | layer | recoverable | what it does |
|---|---|---|---|---|
| `trailing_comma` | syntax | body | yes | a comma after the last element of an object or array |
| `missing_comma` | syntax | body | yes | one structural comma between elements is dropped |
| `single_quotes` | syntax | body | yes | strings quoted with ' instead of ", Python-dict style |
| `unquoted_keys` | syntax | body | yes | identifier-like object keys lose their quotes ({key: ...}) |
| `python_literals` | syntax | body | yes | True / False / None instead of true / false / null |
| `smart_quotes` | syntax | body | yes | typographic “quotes” replace every straight " delimiter |
| `line_comment` | syntax | body | yes | a // comment appended to one line of the JSON |
| `block_comment` | syntax | body | yes | a /* block comment */ right after the opening brace |
| `unescaped_newline` | syntax | body | yes | a raw line break inside a string value instead of \n |
| `nan_infinity` | syntax | body | no | a numeric field becomes NaN, Infinity, or -Infinity |
| `nonstandard_numbers` | syntax | body | yes | a number written as +42, .5, -042, or 1_000 |
| `fullwidth_punct` | syntax | body | yes | full-width ： and ， replace every structural : and , |
| `ellipsis_item` | structure | body | yes | an '...' placeholder appended as if more items follow |
| `jsonl_spray` | structure | body | yes | an array is emitted as one bare object per line (JSONL) |
| `double_encoded` | structure | body | yes | the JSON is serialized twice: a string containing JSON |
| `duplicate_output` | structure | body | yes | the entire JSON document is emitted twice in a row |
| `self_correction` | structure | body | yes | a broken first attempt, an apology, then the real JSON |
| `unbalanced` | structure | body | yes | the final closing brace or bracket never arrives |
| `html_escaped` | noise | body | yes | every " becomes &quot;, & becomes &amp;, and so on |
| `fence` | wrapper | wrap | yes | the JSON wrapped in a ```json markdown fence |
| `fence_unclosed` | wrapper | wrap | yes | an opening ```json fence with no closing fence |
| `fence_wrong_lang` | wrapper | wrap | yes | a fence tagged ```python, ```JSON, ```js, or similar |
| `fence_double` | wrapper | wrap | yes | a stuttered double fence: ```json on two lines running |
| `chatter` | wrapper | wrap | yes | conversational prose before and/or after the JSON |
| `prose_inside_fence` | wrapper | wrap | yes | an explanatory sentence inside the fence, after the JSON |
| `tag_wrap` | wrapper | wrap | yes | the JSON wrapped in <json>/<answer>-style XML tags |
| `thinking_leak` | wrapper | wrap | yes | a leaked <thinking> block precedes the JSON answer |
| `special_tokens` | wrapper | stream | yes | an end-of-sequence token leaks after the answer |
| `truncated` | structure | stream | no | the transcript stops mid-token at 55-92% of its length |
| `truncated_string` | structure | stream | no | the transcript stops in the middle of a quoted string |
| `invisible_chars` | noise | stream | yes | zero-width spaces, NBSPs, and a possible BOM sprinkled in |

## Where these come from

Each shape emulates a failure mode that is widely reported by developers
parsing model output — markdown fences around "raw JSON" answers, Python
`repr()` bleeding through (`single_quotes` + `python_literals`), `max_tokens`
truncation, repetition loops, chat-template mismatches leaking `<|im_end|>`,
double-stringified tool arguments, and copy-paste chains injecting zero-width
characters. The `note` field on every shape (shown by `sloppygen explain`)
describes the mechanism in one or two sentences.

Two deliberate design rules keep the catalog honest:

1. **Body mutations are token-aware.** A shape that re-quotes strings
   re-quotes exactly the string tokens; a dropped comma is a structural
   comma. String *contents* are never accidentally corrupted, so every
   sample tests the defect it claims to test.
2. **Value preservation is tracked.** `nonstandard_numbers` only respells a
   number (`1_000`, `+42`, `.5`, `-042`); `nan_infinity` destroys it. That is
   why one is recoverable and the other is not.

## Stability and versioning

Registry order is part of the determinism contract: a corpus is fully
defined by `(sloppygen version, seed, payload, options)`. Within a minor
version line, new shapes are appended, never inserted or reordered. Any
change to an existing shape's output for the same `(seed, index)` is a
breaking change and gets a version bump plus a CHANGELOG entry.
