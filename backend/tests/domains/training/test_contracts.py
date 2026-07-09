"""V3 contract fidelity: the shipped Block 0 artifacts are the parsing contract."""

from __future__ import annotations

import json

import pytest
from pydantic import TypeAdapter, ValidationError

from app.domains.training.contracts import (
    Cmp,
    ExerciseLibrary,
    NotPredicate,
    Predicate,
    SignalRegistry,
    V3Block,
    V3Bundle,
)
from tests._architecture import REPO_ROOT

BLOCK0 = REPO_ROOT / "docs" / "routine-pivot" / "block0"


def _load(name: str) -> dict:
    return json.loads((BLOCK0 / name).read_text(encoding="utf-8"))


@pytest.mark.parametrize("name", ["running_v3.json", "strength_v3.json", "support_v3.json"])
def test_shipped_bundles_parse_and_round_trip(name: str):
    raw = _load(name)
    bundle = V3Bundle.model_validate(raw)
    assert V3Bundle.model_validate(bundle.model_dump(exclude_none=True)) == bundle


def test_shipped_block_parses_including_artifact_only_fields():
    block = V3Block.model_validate(_load("block0.json"))
    assert block.flat_weeks == [1, 2, 3]
    assert block.step_response is not None and block.step_response.target_fraction == 0.67
    assert len(block.scheduling_constraints) == 3


def test_shipped_registry_and_library_parse():
    registry = SignalRegistry.model_validate(_load("registry.json"))
    assert len(registry.state_vector) == 5
    library = ExerciseLibrary.model_validate(_load("exercise_library.json"))
    assert any(e.id == "pendulum_squat" for e in library.exercises)


def test_unknown_keys_are_rejected():
    raw = _load("block0.json")
    raw["surprise"] = 1
    with pytest.raises(ValidationError):
        V3Block.model_validate(raw)


def test_contract_kind_discriminates():
    raw = _load("strength_v3.json")
    assert {c["contract"]["kind"] for c in raw["cards"]} == {"overload"}
    bundle = V3Bundle.model_validate(raw)
    assert all(card.contract.kind == "overload" for card in bundle.cards)


def test_block0_exit_criteria_all_predicate_and_bool_value_round_trip():
    """block0.json's `e1rm_initialized` criterion nests Cmp under AllPredicate,
    and two other criteria compare against a bare JSON boolean — neither shape
    appears in the three bundles, so this is covered directly against the
    canon artifact rather than inferred from the bundle round-trip test.
    """
    block = V3Block.model_validate(_load("block0.json"))
    by_id = {c.id: c.predicate for c in block.exit_criteria}
    assert isinstance(by_id["lthr_anchored"], Cmp)
    assert by_id["lthr_anchored"].value is True
    assert isinstance(by_id["e1rm_initialized"].all[0], Cmp)  # type: ignore[union-attr]


def test_not_predicate_synthetic_round_trip():
    """No shipped artifact uses the `not` predicate key, but the schema spec
    defines it, so it is exercised here with a synthetic payload rather than
    against canon. Tests both default and by_alias serialization.
    """
    raw = {"not": {"signal": "flag.tissue.quad", "op": "==", "value": True}}
    adapter = TypeAdapter(Predicate)
    parsed = adapter.validate_python(raw)
    assert isinstance(parsed, NotPredicate)
    # default dump round-trips via populate_by_name
    assert adapter.validate_python(parsed.model_dump(exclude_none=True)) == parsed
    # by_alias dump uses the wire key "not"
    dumped = parsed.model_dump(by_alias=True, exclude_none=True)
    assert "not" in dumped
    assert "not_" not in dumped
    assert adapter.validate_python(dumped) == parsed


def test_cmp_in_operator_accepts_value_list():
    """The 'in' operator accepts a list of literal values."""
    cmp = Cmp.model_validate({"signal": "x", "op": "in", "value": [1, 2.5, "a", True]})
    assert cmp.value == [1, 2.5, "a", True]
