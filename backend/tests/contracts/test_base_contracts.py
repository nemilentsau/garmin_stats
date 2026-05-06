"""Tests for shared Pydantic contract base classes."""

from app.contracts.base import DefaultsRequired


class ExampleContract(DefaultsRequired):
    required_value: int
    nullable_default: str | None = None


def test_defaults_required_marks_defaulted_fields_as_required_for_serialization():
    schema = ExampleContract.model_json_schema(mode="serialization")

    assert schema["required"] == ["required_value", "nullable_default"]
