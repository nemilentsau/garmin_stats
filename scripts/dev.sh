#!/usr/bin/env bash
# Launch backend + frontend on arbitrary ports.
# Usage: ./scripts/dev.sh [BACKEND_PORT] [FRONTEND_PORT]
# Defaults: backend=8000, frontend=5173

set -euo pipefail

BACKEND_PORT="${1:-8000}"
FRONTEND_PORT="${2:-5173}"

BACKEND_URL="http://localhost:${BACKEND_PORT}"
FRONTEND_URL="http://localhost:${FRONTEND_PORT}"

cleanup() {
    echo ""
    echo "Shutting down..."
    kill "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null || true
    wait "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo "Starting backend on :${BACKEND_PORT}, frontend on :${FRONTEND_PORT}"

# Backend — set CORS to allow the frontend origin
BACKEND_CORS_ORIGINS="${FRONTEND_URL},http://127.0.0.1:${FRONTEND_PORT}" \
    uv run --directory "${PROJECT_DIR}/backend" \
    uvicorn app.main:app --reload --port "${BACKEND_PORT}" &
BACKEND_PID=$!

# Frontend — point at the backend
PUBLIC_API_BASE_URL="${BACKEND_URL}" \
    npm run --prefix "${PROJECT_DIR}/frontend" \
    dev -- --port "${FRONTEND_PORT}" &
FRONTEND_PID=$!

wait
