# Routine Artifact Bundle Spec

This document defines the only supported high-level routine import contract for the app.

If you are converting a freeform source document, markdown note, or program outline into something the app can use, this is the target format.

The app does not ingest arbitrary markdown. It ingests one structured JSON bundle, previews it without writes, imports it as inert drafts, and only then allows explicit activation into the live runtime.

## Canonical Flow

The supported flow is:

`source document -> LLM emits proper bundle JSON -> preview -> import drafts -> activate -> Today/Schedule`

Important implications:

- the LLM conversion step happens outside the runtime
- preview must not write to live tables
- import writes only `assistant_artifacts`
- activation is the only step that compiles live `card_templates`, `routine_schedules`, and `routine_assignments`

`/programs` is not part of this workflow. It is intentionally parked while routines use the assistant artifact runtime.

## What The App Accepts

The app accepts one top-level JSON object with this shape:

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

Field requirements:

- `id`: stable bundle identifier
- `name`: human-readable bundle name
- `schema_version`: currently `1`
- `description`: optional plain-language summary
- `card_templates`: reusable card template specs
- `routine_specs`: deterministic routine schedule specs

At least one of `card_templates` or `routine_specs` must be present.

## Determinism Rule

The bundle must be deterministic before it reaches preview.

Allowed:

- fixed weekly or biweekly cadence
- explicit start and optional end dates
- explicit weekday, slot, and position
- fixed card references
- assignment-level prescription overrides

Not allowed inside the bundle:

- conditional branching such as "do A or B depending on how you feel"
- runtime decisions such as "skip this if tired"
- open-ended recurrence like "every few days"
- experiments, hypotheses, or analysis instructions mixed into schedule records
- requests for a new renderer family disguised as payload fields

If the source material contains conditionals, resolve them before emitting bundle JSON.

Example:

- Source: "Open Monitoring, or Extended Exhale if activated/restless"
- Bundle output: schedule `Open Monitoring`
- Add fallback text to assignment instructions: "If you feel activated or restless, switch to Extended Exhale."

The bundle must describe one schedule the runtime can project without guessing.

## Card Reuse vs New Card Creation

This is the most important modeling rule.

Reuse a card template when the renderer family and interaction model are the same.

Use `prescription_override_json` on the assignment when the difference is only:

- duration
- breathing pattern
- instructions
- prompts
- progression dose
- notes specific to one scheduled occurrence pattern

Create a new card template only when the user-facing interaction model changes.

Examples:

- `Focused Attention` at 10 minutes and `Focused Attention` at 12 minutes should usually be one card template plus assignment overrides.
- `Resonance Breathing` and `Focused Attention` should usually be separate card templates because the protocol and instructions are materially different, even if both use `timer_session`.
- A protocol that needs a brand-new UI interaction is not another card template. It is a new renderer capability and is out of scope for bundle import.

## ID Conventions

Use stable, lowercase, kebab-case ids.

Recommended conventions:

- bundle id: `two-week-meditation-foundation`
- card template id: `meditation-focused-attention`
- routine id: `two-week-meditation-foundation-routine`
- assignment id: `two-week-meditation:week2-thu-midday-focused-attention`

Guidelines:

- ids must be stable across revisions when the conceptual object is the same
- assignment ids must be unique within the bundle
- do not use random UUIDs unless you truly cannot derive a stable semantic id

Stable ids matter because preview/import needs to distinguish create vs update behavior.

## Bundle Components

### `card_templates`

Each entry must match the runtime `CardTemplateSpec`.

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

If the source routine needs something outside those families, stop and create a capability request through the single-artifact flow instead of forcing it into a bundle.

### `routine_specs`

Each entry must match the runtime `RoutineSpec`.

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

Supported cadence values in v1:

- `weekly`
- `biweekly`

### `assignments`

Each assignment links a reusable card template into a recurring schedule slot.

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

- weekly routines must use `cycle_week = 1`
- biweekly routines must use `cycle_week = 1` or `2`
- every `card_template_id` must resolve either to a bundled `card_template` or an already-existing live/validated card template

## Unsupported Source Structures

The LLM must not pass these through directly:

- branching schedules
- state-machine logic
- "if missed, make up tomorrow" rules
- experiment protocols mixed with routines
- multiple alternative programs in one bundle
- prose-only instructions without structured assignments

When the source contains unsupported structures, normalize it first:

- split experiments out entirely
- collapse branches into one deterministic path plus notes
- split multiple programs into multiple bundles
- translate prose schedules into explicit assignments

If that normalization cannot be done faithfully, stop and return an issue instead of fabricating schedule data.

## Validation Expectations

Preview should reject:

- malformed bundle shape
- duplicate card ids inside the bundle
- duplicate routine ids inside the bundle
- duplicate assignment ids inside the bundle
- unknown card references
- invalid cadence/week combinations
- unsupported renderer families

Import should only succeed when preview is clean.

Import does not create live runtime records. It only creates validated draft artifacts.

## Activation Expectations

After import:

- activate card/routine drafts explicitly from `/routines/creation`
- routine activation compiles dependent cards as needed
- live runtime data then appears in `/routines/schedule` and `/today`

Activation is where the bundle becomes live behavior.

## Example

The checked-in example bundles are:

- [`docs/two_week_meditation_bundle.json`](/Users/andreinemilentsau/Projects/garmin_stats/docs/two_week_meditation_bundle.json)
- [`docs/two_week_core_bundle.json`](/Users/andreinemilentsau/Projects/garmin_stats/docs/two_week_core_bundle.json)

That file is the reference implementation of this spec for a two-week meditation routine starting on `2026-03-16`.
