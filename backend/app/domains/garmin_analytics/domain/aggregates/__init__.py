"""Aggregate Garmin analytics read-model calculations.

Daily aggregates summarize one `DayData`; period aggregates summarize raw
readings across a window. Period stats intentionally do not average daily
aggregate fields unless the metric policy explicitly says so.
"""
