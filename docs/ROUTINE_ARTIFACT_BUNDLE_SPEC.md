# Routine Artifact Bundle Spec

This is the current high-level import contract for assistant-authored routine
content.

The app does not ingest arbitrary markdown. It accepts deterministic JSON,
previews it without writes, imports validated artifacts, and auto-activates
them into the live routine runtime.

## Canonical Flow

```text
source material -> bundle JSON -> preview -> import -> auto-activate -> schedule/today
```

Important implications:

- markdown-to-bundle conversion happens outside the runtime
- preview performs no writes
- import persists validated artifacts before activation
- card templates activate before routines because routines reference cards
- Schedule and Today only read live compiled routine records

## Top-Level Shape

```json
{
  "id": "two-week-meditation-foundation",
  "name": "Two-Week Meditation Foundation",
  "schema_version": 1,
  "description": "Optional summary",
  "card_templates": [],
  "routine_specs": []
}
```

Rules:

- `id` is stable lowercase kebab-case.
- `name` is human-readable.
- `schema_version` is currently `1`.
- At least one of `card_templates` or `routine_specs` must be present.
- The bundle is deterministic before preview. Vague recurrence such as "every
  few days" must already be normalized to concrete assignment days.

## Card Templates

Each `card_templates[]` item must match `CardTemplateSpec`.

Required fields:

- `id`
- `name`
- `renderer`
- `slot_default`
- `payload`

Optional fields:

- `summary`
- `tags`

Supported renderer families:

- `timer_session`
- `checklist_block`
- `exercise_block`

If the source material needs another interaction model, stage a
`capability_request` artifact instead of forcing unsupported behavior into a
card payload.

## Routine Specs

Each `routine_specs[]` item must match `RoutineSpec`.

Required fields:

- `id`
- `name`
- `start_date`
- `assignments`

Optional fields:

- `end_date`
- `status`
- `tags`
- `notes`

Routines do not carry cadence fields. The artifact layer accepts explicit
day-relative assignments and activation compiles them into dated
`RoutineAssignment` rows.

## Assignments

Each `assignments[]` item must match `RoutineActivationAssignment`.

Required fields:

- `id`
- `card_template_id`
- `day`
- `slot`

Optional fields:

- `position`
- `prescription_override_json`

Rules:

- `day` is 1-based relative to the routine `start_date`.
- Every `card_template_id` must resolve to either a bundled card template, an
  already validated/activated card artifact, or an existing live card template.
- Assignment ids must be unique within the bundle and must not collide with an
  assignment already owned by another routine.
- Multiple assignments on the same date are valid and expected when a protocol
  requires multiple sessions.

Example assignment:

```json
{
  "id": "two-week-meditation:day8-midday-box",
  "card_template_id": "meditation-box-breathing",
  "day": 8,
  "slot": "midday",
  "position": 10,
  "prescription_override_json": {
    "duration_minutes": 6,
    "instructions": "Keep the rhythm easy; stop if breathing feels forced."
  }
}
```

## Card Reuse

Reuse a card template when the interaction model is the same.

Use assignment-level `prescription_override_json` when the difference is only:

- duration
- instructions
- prompts
- pattern
- dose or progression

Create a new card template only when the user-facing interaction type materially
changes.

## Preview Expectations

Preview rejects:

- malformed bundle shape
- placeholder or demo content
- duplicate card ids
- duplicate routine ids
- duplicate assignment ids
- unknown card references
- unsupported renderer families
- assignment ids already owned by another live or staged routine

Preview is the validation boundary. It must not write artifacts, cards,
routines, assignments, or logs.

## Import Expectations

If preview is clean, import should:

1. Persist the validated artifacts.
2. Activate card templates first.
3. Activate routines after card dependencies exist.
4. Leave the live result visible in `/routines/schedule` and `/today`.

The normal bundle flow does not require a separate manual activation step.
Low-level assistant-artifact APIs may still expose manual activation for
debugging or one-off flows, but that is not the canonical path.

## Checked-In Examples

- [docs/two_week_core_bundle.json](/Users/andreinemilentsau/Projects/garmin_stats/docs/two_week_core_bundle.json)
- [docs/two_week_meditation_bundle.json](/Users/andreinemilentsau/Projects/garmin_stats/docs/two_week_meditation_bundle.json)
