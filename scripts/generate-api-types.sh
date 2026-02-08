#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

# Export OpenAPI spec from FastAPI (no server needed)
cd backend
uv run python -c "
import json
from app.main import app
with open('../frontend/openapi.json', 'w') as f:
    json.dump(app.openapi(), f, indent=2)
"
cd ..

# Generate TypeScript types from OpenAPI spec
cd frontend
npx openapi-typescript openapi.json -o src/lib/api-types.ts
