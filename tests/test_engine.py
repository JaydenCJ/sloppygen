"""Engine invariants that hold across the whole catalog.

The core promise: every sample is *genuinely* corrupted — feeding it to
``json.loads`` either fails or yields something other than the expected
payload. A shape that accidentally emits clean output is a useless shape,
and this file is where it gets caught.
"""

from __future__ import annotations

import json

import pytest

from sloppygen import Sample, canonicalize, generate
from sloppygen.errors import CompositionError
from sloppygen.registry import all_shapes


def test_every_shape_genuinely_corrupts(payload, array_payload):
    for shape in all_shapes():
        target = array_payload if shape.id == "jsonl_spray" else payload
        sample = generate(target, shape.id, seed=11)
        assert sample.text != canonicalize(target), shape.id
        try:
            value = json.loads(sample.text)
        except ValueError:
            continue  # not JSON at all: corrupted, as advertised
        # double_encoded stays valid JSON but must not equal the payload.
        assert value != target, f"{shape.id} produced a clean payload"


def test_sample_metadata_is_complete_and_canonicalize_is_stable(payload):
    sample = generate(payload, "fence", seed=5, index=3)
    assert sample.id == "0003-fence"
    assert sample.shapes == ("fence",)
    assert sample.category == "wrapper"
    assert sample.seed == 5 and sample.index == 3
    assert sample.expected == payload
    # The canonical form shapes mutate: pretty, 2-space, unicode preserved.
    text = canonicalize({"city": "Zürich", "n": 1})
    assert '"city": "Zürich"' in text
    assert text.startswith("{\n  ")


def test_stacked_shapes_apply_in_layer_order(payload):
    # body (trailing_comma) -> wrap (fence) -> stream (special_tokens),
    # whatever order the caller wrote them in.
    sample = generate(payload, "special_tokens+trailing_comma+fence", seed=2)
    assert sample.shapes == ("trailing_comma", "fence", "special_tokens")
    assert sample.text.startswith("```json\n")
    assert not sample.text.endswith("```")  # the leaked token comes last


def test_stack_recoverable_is_conjunction(payload):
    assert generate(payload, "trailing_comma+fence", seed=2).recoverable is True
    assert generate(payload, "trailing_comma+truncated", seed=2).recoverable is False


def test_invalid_stacks_are_rejected(payload):
    with pytest.raises(CompositionError):  # two shapes on one layer
        generate(payload, "trailing_comma+missing_comma", seed=2)
    with pytest.raises(CompositionError):  # more than three shapes
        generate(payload, ["trailing_comma", "fence", "truncated", "chatter"], seed=2)
    with pytest.raises(CompositionError):  # no shapes at all
        generate(payload, [], seed=2)


def test_record_round_trip(payload):
    sample = generate(payload, "chatter+unbalanced", seed=8, index=12)
    clone = Sample.from_record(json.loads(json.dumps(sample.to_record())))
    assert clone == sample
