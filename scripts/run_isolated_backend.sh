#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMPDIR="$(mktemp -d "${TMPDIR:-/tmp}/garmin-isolated-backend.XXXXXX")"

cleanup() {
	if [[ "${KEEP_TMP:-0}" == "1" ]]; then
		printf 'Keeping isolated backend workspace at %s\n' "$TMPDIR"
		return
	fi
	rm -rf "$TMPDIR"
}

trap cleanup EXIT

export GARMIN_DB_PATH="$TMPDIR/test.db"
export GARMIN_DATA_DIR="$TMPDIR/data"

mkdir -p "$GARMIN_DATA_DIR"

printf 'Starting isolated backend with:\n'
printf '  GARMIN_DB_PATH=%s\n' "$GARMIN_DB_PATH"
printf '  GARMIN_DATA_DIR=%s\n' "$GARMIN_DATA_DIR"
printf '  KEEP_TMP=%s\n' "${KEEP_TMP:-0}"

cd "$ROOT_DIR/backend"
exec uv run uvicorn app.main:app --reload "$@"
