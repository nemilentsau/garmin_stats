"""Shared Pydantic contract base classes."""

from pydantic import BaseModel, ConfigDict


class DefaultsRequired(BaseModel):
    """Require defaulted fields in OpenAPI serialization schemas."""

    model_config = ConfigDict(json_schema_serialization_defaults_required=True)
