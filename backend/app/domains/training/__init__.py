"""V3-native training domain.

Owns the v3 wire contracts (`contracts.py`) that parse the Block 0 artifacts
under `docs/routine-pivot/block0/` — the bundles, block, signal registry, and
exercise library that replace the routines-domain draft/compiled model for
training content. Later tasks in this package add the import workflow that
turns these contracts into the live runtime the `routines` domain serves.
"""
