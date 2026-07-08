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
  "schema_version": 2,
  "description": "Optional summary",
  "card_templates": [],
  "routine_specs": []
}
```

Rules:

- `id` is stable lowercase kebab-case.
- `name` is human-readable.
- `schema_version` is `2`. Bundles at version 1 (legacy `renderer` field) are
  not accepted; re-author them to the typed `card_type` payload schema below.
- At least one of `card_templates` or `routine_specs` must be present.
- The bundle is deterministic before preview. Vague recurrence such as "every
  few days" must already be normalized to concrete assignment days.

## Card Templates

Each `card_templates[]` item must match `CardTemplateSpec`.

Required fields:

- `id`
- `name`
- `slot_default`
- `payload`

Optional fields:

- `summary`
- `tags`

`payload` must be a typed payload object carrying a `card_type` discriminator.
The five supported card types are:

### `running_workout`

```json
{
  "card_type": "running_workout",
  "workout_type": "easy",
  "rpe": "4-5 / 10",
  "talk_test": "full sentences",
  "hr_guidance": "Z2, below 145 bpm",
  "calibration_quality": false,
  "instructions": "...",
  "segments": [
    { "id": "warmup", "label": "Warm-up", "kind": "warmup", "prescription": "10 min" }
  ],
  "post_run_fields": [
    { "key": "temp_c", "label": "Temperature (°C)", "field_type": "number" }
  ]
}
```

- `workout_type` — string label for the run type (e.g. `easy`, `long_easy`,
  `steady`, `progression`, `lthr_test`).
- `segments` — ordered list; `kind` is one of `warmup`, `main`, `strides`,
  `cooldown`, `intervals`; `prescription` is a flexible range string
  (e.g. `"35-50 min"`).
- `post_run_fields` — optional per-run confounder fields collected after the
  run (weather, terrain, gear). Each carries `key`, `label`, `field_type`
  (`number` or `text`), and optional `unit`.

### `strength_session`

```json
{
  "card_type": "strength_session",
  "session_focus": "Chest + Side Delts",
  "duration_minutes": 50,
  "rir_guidance": "1-3 reps in reserve",
  "instructions": "...",
  "exercises": [
    { "id": "bench", "label": "Bench Press", "set_scheme": "3x5-8" }
  ],
  "rating_prompts": [
    { "key": "pump", "label": "Pump quality", "scale_min": 1, "scale_max": 5 }
  ]
}
```

- `set_scheme` is a range string such as `"3x5-8"` (sets × rep-range).
- `rating_prompts` replace the old fake `post_session_ratings` exercise row.

### `breath_timer`

```json
{
  "card_type": "breath_timer",
  "duration_minutes": 5,
  "pattern_label": "4s in / 4s hold / 4s out / 4s hold",
  "instructions": "..."
}
```

- `pattern_label` is the human-readable prescription; the watch is the timer,
  so the card carries no animation or per-phase timing. The breath card logs a
  single optional subjective signal, `ratings.felt_downshift` (1=Barely,
  2=Somewhat, 3=Strongly) — it has no `rating_prompts`.

### `meditation_timer`

```json
{
  "card_type": "meditation_timer",
  "duration_minutes": 10,
  "technique": "focused_attention",
  "anchor": "exhale count",
  "instructions": "...",
  "rating_prompts": []
}
```

### `checklist`

```json
{
  "card_type": "checklist",
  "instructions": "...",
  "items": [
    { "id": "strap", "label": "HR strap on and reading" }
  ],
  "domain": "running"
}
```

- `domain` is optional (`running`, `strength`, `breathwork`, `meditation`);
  used for visual theming on review and setup cards.

### Checklist item kind

`items[].kind` is `"checkbox"` (default) or `"tissue_check"`. `checkbox`
items are answered with a boolean `checked`/free-text `text`. `tissue_check`
items are answered with a 0-3 soreness scale and a pain flag instead of a
checkbox — used for the per-tissue morning check-in.

```json
{ "id": "tissue.quad", "label": "Quad", "kind": "tissue_check" }
```

### Checklist answers

Logged `ChecklistActual.answers[]` entries carry `checked`/`text` for
`checkbox` items, or `scale`/`flagged` for `tissue_check` items:

```json
{ "item_id": "tissue.quad", "scale": 2, "flagged": true }
```

- `scale` — 0-3 soreness rating (0 = none, 3 = severe); `ge=0, le=3`.
- `flagged` — `true` when the athlete flags pain, not just soreness.

### Session variants (`variant_options`, `selection_rule`)

`running_workout`, `strength_session`, and `checklist` payloads may carry
`variant_options` (plain-language names of alternate versions of the
session) and `selection_rule` (a plain-language sentence describing when to
pick which variant). Both default to empty (`[]` / `null`) — most cards have
no variants.

```json
{
  "variant_options": ["standard", "reduced volume"],
  "selection_rule": "Pick reduced volume if quad soreness >= 2 or pain is flagged this morning."
}
```

Which variant the athlete actually performed is recorded as free text on the
card log via `variant_taken` (mirrors `notes` on `CardLog` /
`TodayCardLogUpdateRequest` / `TodayCard`), not as a structured reference
back into `variant_options`.

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
- segments or phase parameters
- dose or progression

Keys in `prescription_override_json` are validated against the target card
type's payload at schedule merge time. Valid fields are applied as overrides;
invalid keys (including `card_type` itself, which is stripped automatically)
are silently ignored. The `card_type` discriminator cannot be overridden.

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
- unknown or missing `card_type` values in card payloads
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

- [routine_bundles/meditation_hrv_experiment.json](routine_bundles/meditation_hrv_experiment.json)
- [routine_bundles/four_weeks_breathwork.json](routine_bundles/four_weeks_breathwork.json)
- [routine_bundles/four_weeks_meditation.json](routine_bundles/four_weeks_meditation.json)
- [routine_bundles/two_week_meditation_bundle.json](routine_bundles/two_week_meditation_bundle.json)
