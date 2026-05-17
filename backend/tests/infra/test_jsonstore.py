"""Tests for shared JSON-store SQL predicate helpers."""

import pytest

from app.infra.jsonstore import JsonStore


def test_json_field_predicate_matches_single_value() -> None:
    store = JsonStore({"records"})

    where_sql, params = store.json_field_predicate("$.status", ("active",))

    assert where_sql == "json_extract(data, '$.status') = ?"
    assert params == ("active",)


def test_json_field_predicate_matches_multiple_values() -> None:
    store = JsonStore({"records"})

    where_sql, params = store.json_field_predicate("$.status", ("active", "draft"))

    assert where_sql == "json_extract(data, '$.status') IN (?, ?)"
    assert params == ("active", "draft")


def test_json_field_predicate_empty_values_match_no_rows() -> None:
    store = JsonStore({"records"})

    where_sql, params = store.json_field_predicate("$.status", ())

    assert where_sql == "0 = 1"
    assert params == ()


def test_json_field_predicate_rejects_unknown_paths() -> None:
    store = JsonStore({"records"})

    with pytest.raises(ValueError, match="Invalid JSON filter path"):
        store.json_field_predicate("$.unexpected", ("value",))


def test_status_predicate_uses_status_field() -> None:
    store = JsonStore({"records"})

    where_sql, params = store.status_predicate(("validated",))

    assert where_sql == "json_extract(data, '$.status') = ?"
    assert params == ("validated",)
