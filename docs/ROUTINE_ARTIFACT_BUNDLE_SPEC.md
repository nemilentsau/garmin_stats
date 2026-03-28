# Routine Artifact Bundle Spec

This is the only supported high-level routine import contract.

The app does not ingest arbitrary markdown. It accepts one deterministic JSON bundle, previews it without writes, then imports and auto-activates it into the live runtime.

## Canonical Flow

`source document -> bundle JSON -> preview -> import -> auto-activate -> schedule/today`

Important implications:

- markdown-to-bundle conversion happens outside the runtime
- preview performs no writes
- bundle import persists artifacts and auto-activates them in dependency order
- Schedule and Today only read live compiled runtime records

## Accepted Shape

The app accepts one top-level object:

```json
{
  "id": "bundle-id",
  "name": "Bundle Name",
  "schema_version": 1,
  "description": "Optional summary",
  "card_templates": [],
  "routine_specs": []
}
```

Rules:

- `id` must be stable
- `name` must be human-readable
- `schema_version` is currently `1`
- at least one of `card_templates` or `routine_specs` must be present

## Determinism Rule

The bundle must already be deterministic before preview.

Allowed:

- explicit cadence
- explicit start date and optional end date
- explicit weekday, slot, and position
- explicit card references
- assignment-level prescription overrides

Not allowed:

- runtime branching such as "do A or B depending on how you feel"
- vague recurrence such as "every few days"
- experiments or analysis instructions mixed into schedule specs
- payload hacks for unsupported renderer families

If the source material is ambiguous, normalize it before producing the bundle.

## IDs

Use stable lowercase kebab-case ids.

Recommended pattern:

- bundle: `two-week-meditation-foundation`
- card: `meditation-focused-attention`
- routine: `two-week-meditation-foundation-routine`
- assignment: `two-week-meditation:week2-thu-midday-focused-attention`

Stable ids matter because preview/import distinguishes create vs update behavior by identity.

## Card Templates

Each `card_templates[]` entry must match the runtime `CardTemplateSpec`.

Required fields:

- `id`
- `name`
- `renderer`
- `slot_default`
- `payload`

Optional fields:

- `summary`
- `tags`

Supported renderer families in v1:

- `timer_session`
- `checklist_block`
- `exercise_block`

If the source needs another interaction model, return a capability request instead of forcing it into the bundle.

## Routine Specs

Each `routine_specs[]` entry must match the runtime `RoutineSpec`.

Required fields:

- `id`
- `name`
- `cadence`
- `start_date`
- `assignments`

Optional fields:

- `end_date`
- `status`
- `tags`
- `notes`

Supported cadence values:

- `weekly`
- `biweekly`

## Assignments

Each assignment places one reusable card into one recurring slot.

Required fields:

- `id`
- `card_template_id`
- `weekday`
- `slot`

Optional fields:

- `cycle_week`
- `position`
- `prescription_override_json`

Rules:

- weekly routines use `cycle_week = 1`
- biweekly routines use `cycle_week = 1` or `2`
- every `card_template_id` must resolve either to a bundled card template or an already-existing live card template

## Card Reuse vs New Cards

Reuse a card template when the interaction model is the same.

Use assignment overrides when the difference is only:

- duration
- instructions
- prompts
- pattern
- dose

Create a new card template only when the interaction model itself changes.

## Preview Expectations

Preview should reject:

- malformed bundle shape
- placeholder or demo content
- duplicate card ids
- duplicate routine ids
- duplicate assignment ids
- unknown card references
- invalid cadence/week combinations
- unsupported renderer families

Preview is the validation boundary. It must not write live runtime data.

## Import Expectations

If preview is clean, import should:

1. persist the validated artifacts
2. auto-activate card templates first
3. auto-activate routines after their card dependencies exist
4. leave the live result visible in `/routines/schedule` and `/today`

The normal bundle flow does not require a separate manual activation step.

Low-level assistant-artifact APIs may still expose manual activation for debugging or one-off flows, but that is not the canonical path.

## Example Bundles

Checked-in examples:

- [docs/morning_stretching_bundle.json](/Users/andreinemilentsau/Projects/garmin_stats/docs/morning_stretching_bundle.json)
- [docs/two_week_core_bundle.json](/Users/andreinemilentsau/Projects/garmin_stats/docs/two_week_core_bundle.json)
- [docs/two_week_meditation_bundle.json](/Users/andreinemilentsau/Projects/garmin_stats/docs/two_week_meditation_bundle.json)
