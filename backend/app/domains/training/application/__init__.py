"""V3 import pipeline: schedule compiler and L1-L12 block validator.

Modules in this package port `docs/routine-pivot/block0/linter.py` onto the
typed contracts in `app.domains.training.contracts`. `compile.py` owns the
linter's schedule-compilation section (day/slot ordering, full-variant
prescription patching, per-entry minute estimation); `validation.py` owns the
L1-L12 rule set that consumes the compiled schedule. Neither module writes
artifacts or imports content into the live routine runtime — that is a later
task's concern.
"""
