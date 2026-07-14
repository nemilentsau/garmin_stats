# core/profile — Charter

**Status:** shipped
**Boundary source of truth for this slice. Update in the same PR that changes it.**

App-level user profile configuration. It owns the stored user profile record and
its persistence contracts, exposed through `/api/profile`. Profile is core app
configuration rather than a product domain, but it still owns its own
persistence boundary and imports no product domain.

## Owns

- App-level user profile configuration.
- Profile persistence contracts.

## Does not own

- Garmin data.
- Routine runtime.
- Experiments.
- Coach behavior.
- Artifacts.
- Journal content.
- Analytics.

## May import

- Profile repository ports and profile-owned contracts.

## Must not import

- Any `app.domains.*` package.
- FastAPI from application modules.
- Unrelated SQLite helpers from application modules.

## Public entrypoints

- `GET /api/profile`
- `PUT /api/profile`
- Profile read/write use cases (`get_user_profile`, `update_user_profile`).

## Key files

- `api.py` — FastAPI router (prefix `/api/profile`); GET returns the current
  profile, PUT creates or replaces it. Resolves `profile_repo` from the
  container and delegates to the application use cases.
- `application.py` — `get_user_profile` (stored profile or empty default) and
  `update_user_profile` (normalizes `id` to `DEFAULT_PROFILE_ID`, persists,
  returns).
- `ports.py` — `ProfileRepository` protocol (`get_profile` / `save_profile`).
- `contracts.py` — `UserProfile` (and `DEFAULT_PROFILE_ID`); the only profile
  contract.
- `adapters.py` — `SqliteProfileRepository`: the persistence boundary, backed by
  the shared `app.infra.jsonstore` over the `user_profile` table.
- `schema.py` — the `user_profile` jsonstore table definition.
