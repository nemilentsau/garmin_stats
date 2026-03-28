# Data Schema Design

This document records the current routine-runtime design. It exists to keep the product boundary stable while experiments are built on top of it.

## Purpose

The routine system is designed so that ordinary routine changes are data changes, not schema migrations or one-off UI projects.

The app should be able to:

- accept structured routine content from the assistant or the user
- validate it before it becomes live behavior
- compile it into reusable runtime records
- project dated occurrences for Schedule and Today without frontend-owned scheduling logic

## Core Rules

### Cards are the primary unit

Cards are the reusable execution unit.

A card is the thing the user sees, the assistant authors, the schedule places, and Today logs.

The schema does not model special-purpose categories like "mindfulness" or "core" as hardcoded database concepts. Those live in names, tags, summaries, and payloads.

### Routines are schedules, not content libraries

A routine defines recurring placement of cards over time.

The content lives in card templates. The routine only defines cadence, date bounds, and recurring assignments.

### Today is execution-only

Today may:

- show projected occurrences
- record completion, partial, or skipped state
- store notes and renderer-specific detail

Today may not:

- create new cards
- create new recurring schedule structure
- become a second schedule-authoring surface

### Creation, Schedule, and Today have different jobs

- Schedule reviews live compiled occurrences and imports bundles
- Today executes and logs one date

Today is still separate from routine authoring, but the current UI keeps routine import and review together on Schedule.

## Runtime Layers

The routine system has three practical layers.

### 1. Bundle contract

The normal authoring/import unit is one deterministic bundle JSON document.

It contains:

- `card_templates`
- `routine_specs`

Preview validates the bundle without writes.

Import persists the bundle artifacts and auto-activates them in dependency order.

### 2. Assistant artifacts

Artifacts are the audit layer between authored specs and live runtime tables.

They capture:

- kind: `card_template`, `routine_spec`, `capability_request`
- schema version
- status
- payload JSON
- validation errors
- optional assistant lineage such as thread or snapshot ids

The normal bundle flow still passes through artifacts, even though bundle import now auto-activates after a successful preview/import decision.

Low-level artifact APIs still exist for manual or debugging flows.

### 3. Live runtime records

These are the records the app actually executes:

- `CardTemplate`
- `RoutineSchedule`
- `RoutineAssignment`
- `CardLog`
- `CardOverride` for previously persisted schedule exceptions still honored by projection

## Live Runtime Records

### CardTemplate

Reusable live card definition with:

- id
- name
- renderer
- default slot
- summary
- tags
- payload JSON
- source artifact linkage

### RoutineSchedule

Live recurring schedule container with:

- id
- name
- status
- cadence
- start date
- optional end date
- tags and notes
- source artifact linkage

### RoutineAssignment

Recurring placement of one card template inside one routine:

- routine id
- card template id
- cycle week
- weekday
- slot
- position
- optional prescription override JSON

### CardLog

Execution record for one dated occurrence:

- date
- occurrence key
- card template id
- optional assignment id
- completion status
- actual JSON
- notes

### CardOverride

Date-specific schedule exceptions from earlier flows.

Important current rule:

- projection still reads persisted overrides for backward compatibility
- Today does not create them

## Renderer Boundary

Renderers are the real infrastructure boundary.

Current supported renderer families:

- `timer_session`
- `checklist_block`
- `exercise_block`

If a routine idea needs a new interaction model, that is a new renderer capability, not another card payload variation. Unsupported requests should surface as `capability_request` artifacts instead of mutating the schema casually.

## Reuse and Overrides

Use one reusable card template when the interaction model is the same.

Use assignment-level `prescription_override_json` when the difference is only:

- duration
- instructions
- prompts
- pattern
- dose or progression

Create a new card template only when the user-facing interaction type materially changes.

## Scheduling Model

The backend owns recurrence resolution.

Schedule and Today both read the same projected 14-day window model from `schedule_projection.py`.

That means:

- the frontend does not implement cadence math
- Schedule and Today stay aligned
- experiments can later reference one live runtime instead of inventing a parallel plan system

Current v1 cadence support:

- `weekly`
- `biweekly`

Current slot buckets:

- `morning`
- `midday`
- `evening`
- `anytime`

## Bundle Flow

Normal bundle flow:

1. Convert source material into deterministic bundle JSON.
2. Preview the bundle.
3. Review validation issues and create/update deltas.
4. Import the bundle.
5. Import persists artifacts and auto-activates them into live runtime records.
6. Review the compiled result in Schedule and Today.

Important consequences:

- preview is the safety boundary
- import is the user decision that makes the bundle live
- the frontend never has to compile routine logic itself

## Assumptions We Intend To Keep

- The frontend stays display-only for analytics and scheduling logic.
- Bundle preview/import is the normal routine-authoring path.
- Cards remain the smallest reusable execution unit.
- Routines remain schedules, not embedded content blobs.
- Schedule is the routine-management surface in the current UI.
- Today remains execution-only.
- Experiments should consume this runtime later instead of bypassing it.

## What Would Count As A Redesign

These changes would require conscious schema redesign, not incidental edits:

- arbitrary user-defined renderer schemas
- Today becoming a schedule editor
- frontend-owned recurrence resolution
- experiments owning a separate routine/execution model
- replacing reusable cards with one-off day-local content blobs
