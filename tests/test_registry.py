"""Registry invariants: the catalog is complete, consistent, and typo-friendly.

Registry order is part of the determinism contract (a corpus is defined by
version + seed + payload + options), so the order itself is pinned here.
"""

from __future__ import annotations

import pytest

from sloppygen.errors import UnknownShapeError
from sloppygen.registry import CATEGORIES, LAYERS, all_shapes, get_shape, shape_ids


def test_registry_has_31_unique_well_formed_shapes():
    shapes = all_shapes()
    assert len(shapes) == 31
    assert len({s.id for s in shapes}) == 31
    for shape in shapes:
        assert shape.category in CATEGORIES, shape.id
        assert shape.layer in LAYERS, shape.id


def test_every_shape_documents_itself():
    for shape in all_shapes():
        assert len(shape.description) > 15, shape.id
        assert len(shape.note) > 40, shape.id


def test_registry_order_is_pinned():
    # Appending new shapes is fine; reordering existing ones breaks the
    # determinism story for published corpora, so head and tail are asserted.
    assert shape_ids()[:5] == [
        "trailing_comma",
        "missing_comma",
        "single_quotes",
        "unquoted_keys",
        "python_literals",
    ]
    assert shape_ids()[-3:] == ["truncated", "truncated_string", "invisible_chars"]


def test_category_and_layer_filters():
    wrappers = all_shapes(categories=["wrapper"])
    assert wrappers and all(s.category == "wrapper" for s in wrappers)
    stream = all_shapes(layers=["stream"])
    assert {s.id for s in stream} == {
        "special_tokens", "truncated", "truncated_string", "invisible_chars",
    }


def test_get_shape_suggests_on_typo_and_points_to_list():
    with pytest.raises(UnknownShapeError) as err:
        get_shape("trailing_commas")
    assert "trailing_comma" in str(err.value)
    with pytest.raises(UnknownShapeError) as err:
        get_shape("zzz")
    assert "sloppygen list" in str(err.value)


def test_unrecoverable_shapes_are_exactly_the_documented_three():
    unrecoverable = {s.id for s in all_shapes() if not s.recoverable}
    assert unrecoverable == {"nan_infinity", "truncated", "truncated_string"}
