#!/usr/bin/env python
"""Generate docs/reference/routes.md from the live FastAPI app + SvelteKit routes.

Backend routes come from the FastAPI OpenAPI schema (the single source of truth
for what is actually mounted). Frontend routes come from walking
frontend/src/routes for `+page.svelte` / `+server.ts`. The output is a generated
doc — never hand-edit it; re-run this script instead:

    cd backend && uv run python ../scripts/generate_routes_doc.py

Run from the repo root or the backend dir; paths resolve from this file.
"""

from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_BACKEND = _REPO_ROOT / "backend"
_FRONTEND_ROUTES = _REPO_ROOT / "frontend" / "src" / "routes"
_OUT = _REPO_ROOT / "docs" / "reference" / "routes.md"


def _load_openapi() -> dict:
    """Prefer importing the app (always current); fall back to a running server."""
    sys.path.insert(0, str(_BACKEND))
    try:
        from app.main import app  # type: ignore

        return app.openapi()
    except Exception as exc:  # noqa: BLE001 - fallback path is intentional
        print(f"  (app import failed: {exc}; trying http://localhost:8000)", file=sys.stderr)
        with urllib.request.urlopen("http://localhost:8000/openapi.json", timeout=5) as resp:
            return json.load(resp)


def _backend_rows(openapi: dict) -> list[tuple[str, str, str]]:
    rows: list[tuple[str, str, str]] = []
    for path, ops in sorted(openapi.get("paths", {}).items()):
        for method, op in ops.items():
            if method.lower() not in {"get", "post", "put", "patch", "delete"}:
                continue
            summary = (op.get("summary") or "").strip()
            rows.append((method.upper(), path, summary))
    return rows


def _group_key(path: str) -> str:
    parts = [p for p in path.split("/") if p and not p.startswith("{")]
    if parts and parts[0] == "api" and len(parts) > 1:
        return parts[1]
    return parts[0] if parts else "(root)"


def _frontend_routes() -> list[str]:
    if not _FRONTEND_ROUTES.exists():
        return []
    routes: set[str] = set()
    for entry in _FRONTEND_ROUTES.rglob("*"):
        if entry.name not in {"+page.svelte", "+server.ts", "+server.js"}:
            continue
        rel = entry.parent.relative_to(_FRONTEND_ROUTES)
        segments = [seg for seg in rel.parts if not (seg.startswith("(") and seg.endswith(")"))]
        url = "/" + "/".join(segments)
        kind = "page" if entry.name == "+page.svelte" else "server"
        routes.add(f"{url or '/'}\t{kind}")
    return sorted(routes)


def main() -> None:
    openapi = _load_openapi()
    rows = _backend_rows(openapi)

    lines: list[str] = []
    lines.append("# Route Inventory")
    lines.append("")
    lines.append("**Status:** generated — do NOT hand-edit. Regenerate after route changes:")
    lines.append("`cd backend && uv run python ../scripts/generate_routes_doc.py`")
    lines.append("")
    lines.append(
        f"Backend from the FastAPI OpenAPI schema ({len(rows)} operations); "
        "frontend from `frontend/src/routes`."
    )
    lines.append("")

    lines.append("## Backend API")
    lines.append("")
    current: str | None = None
    for method, path, summary in sorted(rows, key=lambda r: (_group_key(r[1]), r[1], r[0])):
        key = _group_key(path)
        if key != current:
            current = key
            lines.append("")
            lines.append(f"### `{key}`")
            lines.append("")
            lines.append("| Method | Path | Summary |")
            lines.append("|---|---|---|")
        lines.append(f"| {method} | `{path}` | {summary} |")

    lines.append("")
    lines.append("## Frontend routes (SvelteKit)")
    lines.append("")
    lines.append("| Route | Kind |")
    lines.append("|---|---|")
    for entry in _frontend_routes():
        url, kind = entry.split("\t")
        lines.append(f"| `{url}` | {kind} |")
    lines.append("")

    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {_OUT} ({len(rows)} backend operations)")


if __name__ == "__main__":
    main()
