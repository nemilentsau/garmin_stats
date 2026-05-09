"""Shared Pydantic contract base classes."""

from typing import Any, ClassVar, Literal

from pydantic import BaseModel, ConfigDict, model_validator

EntityStatus = Literal["active", "retired", "paused"]


class DefaultsRequired(BaseModel):
    """Require defaulted fields in OpenAPI serialization schemas."""

    model_config = ConfigDict(json_schema_serialization_defaults_required=True)


class AutoTotalResponse(DefaultsRequired):
    """Response base that auto-computes ``total`` from the items list field.

    Subclasses declare which field holds the items via ``__init_subclass__``::

        class FoosResponse(AutoTotalResponse, items_field="foos"):
            foos: list[Foo] = []
            total: int = 0

    If ``total`` is supplied explicitly it is respected; otherwise it is set
    to ``len(items_field)``.
    """

    _items_field: ClassVar[str]

    def __init_subclass__(cls, items_field: str = "", **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        if items_field:
            cls._items_field = items_field

    @model_validator(mode="before")
    @classmethod
    def _auto_fill_total(cls, data: Any) -> Any:
        if isinstance(data, dict) and "total" not in data:
            items = data.get(cls._items_field)
            if isinstance(items, list):
                data["total"] = len(items)
        return data


class StrictDefaultsRequired(DefaultsRequired):
    """Defaults-required base that also rejects unknown keys."""

    model_config = ConfigDict(
        json_schema_serialization_defaults_required=True,
        extra="forbid",
    )
