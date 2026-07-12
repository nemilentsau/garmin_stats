"""Deterministic coach runtime paths."""

from pathlib import Path


def library_panel_path(
    cache_dir: Path,
    run_id: str,
    fingerprint: str,
    *,
    spec_version: int,
) -> Path:
    """Return the content-addressed historical panel path."""
    return cache_dir / f"{run_id}-{fingerprint}-v{spec_version}.png"
