"""Recovery-score domain: the validated single-axis recovery index + health flags.

Owns the computation behind the dashboard overview — per-metric expanding robust-z
normalization, correlation-deflated weighting, seeded MA7 smoothing, meaningful-change
thresholds, the two health flags, and the evidence assembly. Each module ports logic
validated in the .claude/finding-runs/2026-06-11-* runs (cited per module). The
frontend is display-only; everything the overview shows is computed here and surfaced
through app.domains.garmin_analytics.contracts.dashboard.
"""
