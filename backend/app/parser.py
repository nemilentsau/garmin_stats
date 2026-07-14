"""Compatibility facade for Garmin FIT parsing.

The parser implementation lives under
``app.domains.garmin_health.infra.fit_parser`` because FIT decoding and
timestamp semantics produce canonical Garmin health contracts.  This module
keeps older imports working for the active ingest API while avoiding new parser
logic at the app root.
"""

from app.domains.garmin_health.infra.fit_parser import (
    get_files_by_day,
    parse_all_days,
    parse_day,
)

__all__ = [
    "get_files_by_day",
    "parse_all_days",
    "parse_day",
]
