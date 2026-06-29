"""Date-window helpers for experiment domain calculations.

Experiment windows are inclusive local-date ranges. The generic inclusive date-range
generator now lives in ``app.utils.timeutil`` (one definition, shared with analytics trend
densification); it is re-exported here so experiment-domain callers keep a local import.
"""

from __future__ import annotations

from app.utils.timeutil import date_range as date_range

__all__ = ["date_range"]
