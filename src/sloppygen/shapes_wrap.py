"""Wrap-layer shapes: text a model puts *around* an intact JSON body.

These are the highest-frequency failures in the wild — the JSON itself is
fine, but it arrives dressed in markdown fences, conversational chatter,
XML-ish tags, or leaked reasoning. All of them are recoverable by
construction: a parser that can locate the balanced value gets the payload
back byte-for-byte.
"""

from __future__ import annotations

from .registry import MutationContext, Shape

# Declared in catalog order; assembled by sloppygen.registry, which owns
# the canonical cross-module ordering.
SHAPES = []

PREAMBLES = (
    "Sure! Here is the JSON you requested:",
    "Certainly — here's the structured output:",
    "Here is the extracted data in JSON format:",
    "Of course. The requested JSON is below:",
    "I've analyzed the input and produced the following JSON:",
)

POSTAMBLES = (
    "Let me know if you need anything else!",
    "I hope this helps! Feel free to ask follow-up questions.",
    "Note that some fields were inferred from context.",
    "Would you like me to explain any of these fields?",
)

_TRAILING_PROSE = (
    "This JSON includes every field you asked for.",
    "All values above were extracted verbatim from the source text.",
    "Note: the score field is normalized to the 0-1 range.",
)

_THOUGHTS = (
    "The user wants structured output. I should include every field from "
    "the source, keep the types consistent, and output only JSON.",
    "Let me identify the entities first, then map them to the schema. The "
    "schema requires name, tags, and a numeric score.",
    "I need to be careful with the optional fields here — null is the "
    "safest choice when the source does not mention them.",
)

_WRONG_LANGS = ("JSON", "Json", "json5", "javascript", "js", "python", "yaml")

_TAGS = ("json", "answer", "output", "result", "response")


def _fence(ctx: MutationContext) -> str:
    return "```json\n" + ctx.text + "\n```"


SHAPES.append(Shape(
    id="fence",
    category="wrapper",
    layer="wrap",
    recoverable=True,
    description="the JSON wrapped in a ```json markdown fence",
    note=(
        "Chat-tuned models format anything code-like as a markdown block, "
        "even when told to reply with raw JSON. The baseline case every "
        "parser must survive."
    ),
    apply=_fence,
))


def _fence_unclosed(ctx: MutationContext) -> str:
    return "```json\n" + ctx.text


SHAPES.append(Shape(
    id="fence_unclosed",
    category="wrapper",
    layer="wrap",
    recoverable=True,
    description="an opening ```json fence with no closing fence",
    note=(
        "The closing fence is the very last thing a model emits, so it is "
        "the first casualty of a stop sequence or token limit."
    ),
    apply=_fence_unclosed,
))


def _fence_wrong_lang(ctx: MutationContext) -> str:
    lang = ctx.rng.choice(_WRONG_LANGS)
    return "```" + lang + "\n" + ctx.text + "\n```"


SHAPES.append(Shape(
    id="fence_wrong_lang",
    category="wrapper",
    layer="wrap",
    recoverable=True,
    description="a fence tagged ```python, ```JSON, ```js, or similar",
    note=(
        "Extractors keyed on the literal string '```json' miss fences with "
        "case drift or a neighbouring language tag."
    ),
    apply=_fence_wrong_lang,
))


def _fence_double(ctx: MutationContext) -> str:
    return "```json\n```json\n" + ctx.text + "\n```"


SHAPES.append(Shape(
    id="fence_double",
    category="wrapper",
    layer="wrap",
    recoverable=True,
    description="a stuttered double fence: ```json on two lines running",
    note=(
        "A sampling stutter repeats the fence opener. Naive split-on-fence "
        "logic now sees an empty first block and a stray fence in the body."
    ),
    apply=_fence_double,
))


def _chatter(ctx: MutationContext) -> str:
    mode = ctx.rng.choice(["pre", "post", "both", "both"])
    pre = ctx.rng.choice(PREAMBLES)
    post = ctx.rng.choice(POSTAMBLES)
    if mode == "pre":
        return pre + "\n\n" + ctx.text
    if mode == "post":
        return ctx.text + "\n\n" + post
    return pre + "\n\n" + ctx.text + "\n\n" + post


SHAPES.append(Shape(
    id="chatter",
    category="wrapper",
    layer="wrap",
    recoverable=True,
    description="conversational prose before and/or after the JSON",
    note=(
        "'Sure! Here is the JSON you requested:' — the canonical failure of "
        "instruction-tuned models, reported against every major API since "
        "structured output existed."
    ),
    apply=_chatter,
))


def _prose_inside_fence(ctx: MutationContext) -> str:
    trailing = ctx.rng.choice(_TRAILING_PROSE)
    return "```json\n" + ctx.text + "\n\n" + trailing + "\n```"


SHAPES.append(Shape(
    id="prose_inside_fence",
    category="wrapper",
    layer="wrap",
    recoverable=True,
    description="an explanatory sentence inside the fence, after the JSON",
    note=(
        "The model keeps talking before it remembers to close the block, so "
        "'take everything between the fences' feeds prose to json.loads."
    ),
    apply=_prose_inside_fence,
))


def _tag_wrap(ctx: MutationContext) -> str:
    tag = ctx.rng.choice(_TAGS)
    if ctx.rng.random() < 0.25:
        return "<" + tag + ">\n" + ctx.text  # closing tag never arrives
    return "<" + tag + ">\n" + ctx.text + "\n</" + tag + ">"


SHAPES.append(Shape(
    id="tag_wrap",
    category="wrapper",
    layer="wrap",
    recoverable=True,
    description="the JSON wrapped in <json>/<answer>-style XML tags",
    note=(
        "Prompt templates that demand tagged answers leak into other calls; "
        "roughly one sample in four also loses its closing tag."
    ),
    apply=_tag_wrap,
))


def _thinking_leak(ctx: MutationContext) -> str:
    thought = ctx.rng.choice(_THOUGHTS)
    return "<thinking>\n" + thought + "\n</thinking>\n\n" + ctx.text


SHAPES.append(Shape(
    id="thinking_leak",
    category="wrapper",
    layer="wrap",
    recoverable=True,
    description="a leaked <thinking> block precedes the JSON answer",
    note=(
        "Reasoning traces escape their delimiters under template mismatches; "
        "the visible output then starts with paragraphs of deliberation."
    ),
    apply=_thinking_leak,
))
