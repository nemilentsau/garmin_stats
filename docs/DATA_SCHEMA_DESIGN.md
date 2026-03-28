# Data Schema Design

This document explains the routine runtime we introduced for the health assistant.

It is not just a table inventory. It records the design intent, the boundaries we are protecting, and the assumptions that must stay true if this product is going to become an LLM-first system instead of another brittle hand-built tracker.

## Problem We Were Solving

The previous routine implementation copied one rough markdown plan too literally.

That caused three structural failures:

1. The data model was tied to one specific routine layout instead of a general system.
2. Today, routines, programs, and experiments were mixed together, so changing one behavior risked breaking several surfaces.
3. Adding a new routine concept looked like an infrastructure task instead of a data task.

That is the opposite of the product direction.

The long-term goal is:

- the health assistant authors structured routine specs
- the app validates and compiles them
- the UI renders them without requiring schema churn, new routes, or custom code for every new routine idea

If ordinary routine evolution requires backend refactors, the model has failed.

## Core Philosophy

### Cards are the primary unit

The smallest first-class unit is the card, not the whole day and not the smallest exercise atom.

A card is the unit that:

- the assistant can author
- the user can see and act on
- the app can schedule
- the app can log
- Today can render consistently

This is the center of the design.

We do not model "mindfulness" or "abs" as special categories in the schema. Those are tags, summaries, and payload details on cards and routines. The schema does not know or care whether a card is breathwork, core work, mobility, or something else.

### Routines are schedules, not content libraries

A routine is not a dumping ground for technique definitions.

A routine means:

- a named schedule container
- with a cadence
- with recurring assignments of cards to dates, weekdays, slots, and positions

The actual content lives in card templates. The routine only decides when those cards should appear.

### Today is a projection, not a stored plan

Today is built from live runtime data at read time:

- active routines
- routine assignments
- date-specific schedule exceptions, if they exist
- card logs

We do not persist a separate daily plan table for normal operation.

That keeps Today flexible and avoids duplicating schedule state in another place that can drift out of sync.

Today is an execution surface, not a schedule authoring surface.

That means Today may:

- show cards
- mark them done
- mark them partial or skipped
- store notes and renderer-specific feedback

That means Today must not:

- create new cards
- create new schedule entries
- create ad hoc day-local plans
- become a second source of truth for schedule structure

### Specs come before runtime

The assistant does not write directly into live runtime tables.

Instead it creates structured artifacts that are:

- stored
- validated
- reviewed
- explicitly activated

Only activation compiles those specs into live cards and schedules.

That gives us auditability, safe failure modes, and a strict boundary between "assistant draft" and "app behavior."

### Renderer family is the real infrastructure boundary

The app does not support arbitrary per-card UI schemas.

That would feel flexible at first and then rot into a hidden programming language inside JSON.

Instead, every card belongs to a known renderer family. In v1:

- `timer_session`
- `checklist_block`
- `exercise_block`

New cards inside those families are data. They should not require code changes.

If the assistant needs a genuinely new interaction model, that is not "just another card." That is a new renderer capability and requires coding work. The system records that as a `capability_request`.

## Why SQLite and JSON, Not NoSQL

We explicitly stayed with SQLite.

The problem was not that SQL was too rigid. The problem was that the original schema encoded product decisions too early and too specifically.

SQLite is still the right fit because we need:

- transactional updates when activating specs
- stable relations between cards, routines, assignments, logs, and overrides
- predictable local storage
- simple operational behavior
- queryability for future assistant context and analysis

We use JSON payloads where variability is real:

- card payload details
- assignment-level prescription overrides
- actual logged values
- artifact payloads and validation errors

So the design is relational at the core, flexible at the edges.

That is a better match than a pure document model because the important invariants are relational:

- this assignment belongs to this routine
- this card log belongs to this occurrence
- this live card came from this artifact
- this override targets this occurrence on this date

## Design Goals

The routine runtime is designed to satisfy these goals:

1. Adding an ordinary new card should be a data operation.
2. Activating a draft should be idempotent.
3. Today should be computed from schedules instead of hardcoded day types.
4. Routines should be extensible without database schema changes.
5. Unsupported interaction needs should fail clearly and create a capability request.
6. Experiments and programs should be able to plug into this model later instead of owning parallel routine logic.

## Layers of the Model

The model has two layers: assistant artifacts and live runtime records.

### 1. Assistant artifact layer

Assistant artifacts are drafts authored by the health assistant or created by the system as part of validation.

They are stored in `AssistantArtifact`.

Fields:

- `kind`: `card_template`, `routine_spec`, `capability_request`
- `schema_version`: explicit contract version
- `status`: draft lifecycle state such as `validated`, `invalid`, `activated`
- `source_thread_id`: optional assistant conversation linkage
- `source_snapshot_id`: optional context snapshot linkage
- `payload_json`: the actual structured draft
- `validation_errors`: structured rejection feedback

This layer exists so drafts are first-class records, not transient blobs passed directly into runtime writes.

### Bundle import layer

The canonical high-level authoring unit is not one isolated artifact. It is one proper bundle JSON document that contains:

- `card_templates`
- `routine_specs`

The bundle itself is a preview/import contract, not a live runtime record.

Its job is to let an assistant or user submit one deterministic package, validate cross-references and duplicates, inspect create/update deltas, and then persist the resulting drafts into `AssistantArtifact`.

That gives us a clean boundary:

- source markdown or arbitrary planning docs stay outside the runtime
- the LLM conversion target is one proper bundle JSON payload
- preview performs no writes
- import writes drafts only
- activation remains the only path into live runtime tables

The documented conversion target for LLMs is [`docs/ROUTINE_ARTIFACT_BUNDLE_SPEC.md`](/Users/andreinemilentsau/Projects/garmin_stats/docs/ROUTINE_ARTIFACT_BUNDLE_SPEC.md).

### 2. Live runtime layer

The runtime layer is what the app actually executes.

It consists of:

- `CardTemplate`
- `RoutineSchedule`
- `RoutineAssignment`
- `CardLog`

This layer is deliberately small.

## Runtime Records

### CardTemplate

`CardTemplate` is the reusable live card definition.

It contains stable metadata:

- identity
- name
- renderer family
- default slot
- summary
- tags
- payload JSON
- source artifact reference

The template is reusable across many routines and dates.

It is not tied to one day.

### RoutineSchedule

`RoutineSchedule` is a live schedule container.

It contains:

- identity
- name
- active/inactive status
- cadence
- start date
- optional end date
- tags and notes
- source artifact reference

It does not contain its own card content. It only defines the schedule frame.

### RoutineAssignment

`RoutineAssignment` connects one card template to one routine schedule recurrence.

It contains:

- the routine id
- the card template id
- cycle week
- weekday
- slot
- position
- optional prescription override JSON

This is the actual scheduling link.

It exists so a card can be reused across many schedules, and one schedule can contain many cards, without duplicating card definitions.

### CardLog

`CardLog` stores what actually happened for one occurrence of one card on one date.

It contains:

- date
- occurrence key
- card template id
- optional assignment id
- completion status
- actual JSON
- notes

This allows:

- one-tap completion
- partial completion
- skipped states
- richer detail capture when needed

The schema does not hardcode every possible logged field. Renderer-specific detail lives in `actual_json`.

### CardOverride

`CardOverride` stores date-specific deviations from the compiled schedule.

If this concept exists, it belongs to the schedule management layer, not to Today itself.

For the current pass, Today still reads previously persisted exceptions for backward compatibility, but it does not create them.

Supported actions at the schedule layer in v1:

- `add`
- `hide`
- `replace`

This keeps the base schedule clean while still allowing future date-specific schedule editing without polluting normal recurring assignments, if we reintroduce it through dedicated schedule management later.

Overrides are intentionally separate from routine assignments because they are exceptions, not schedule definitions.

## Spec Contracts

### CardTemplateSpec

This is the assistant-authored contract for creating a card.

It includes:

- `id`
- `name`
- `renderer`
- `slot_default`
- `summary`
- `tags`
- `payload`

The payload shape depends on the renderer family, but the outer contract is stable.

### RoutineSpec

This is the assistant-authored contract for creating a routine schedule.

It includes:

- routine metadata
- cadence
- start and end dates
- tags and notes
- a list of recurring assignments

Assignments reference card template ids. That means routines are schedule composition, not embedded content blobs.

### ArtifactBundleSpec

This is the canonical high-level contract for importing routine content into the app.

It includes:

- bundle metadata
- `card_templates`
- `routine_specs`

It does not compile anything directly.

Instead it supports this flow:

1. preview the whole bundle
2. inspect blocking issues and create/update deltas
3. import validated drafts into `AssistantArtifact`
4. explicitly activate the resulting artifacts

This is the intended path for LLM-authored routine content.

### CapabilityRequestSpec

This is the system's escape hatch when the assistant asks for something the app cannot render safely.

It records:

- the requested renderer
- the reason
- the source artifact id
- an example payload

This prevents silent failure and prevents us from pretending a missing UI capability can be faked by weak generic components.

## Renderer Philosophy

Renderers are product-level capabilities, not convenience labels.

We intentionally locked v1 to three families because each family represents a different interaction pattern:

- `timer_session`: duration, pacing, reflective ratings
- `checklist_block`: a list of items with completion states
- `exercise_block`: repeated movement/exercise items with reps, duration, or sequence detail

This allows wide data flexibility without allowing arbitrary UI semantics.

The hidden assumption is important:

If two cards can use the same renderer family, they should feel like the same interaction type to the user.

If they do not, we probably need a new renderer family instead of abusing the payload shape.

## Card Reuse And Assignment Overrides

The runtime does support per-assignment prescription overrides.

That means we do not need one card template per exact session prescription.

The rule is:

- reuse a card template when the renderer family and interaction model are the same
- use `prescription_override_json` for duration, pattern, instructions, prompts, and dose changes
- create a new card template only when the interaction model materially changes

This matters because a bundle should model a routine as reusable cards plus scheduled overrides, not as a huge pile of near-duplicate card templates.

## Activation and Compilation Flow

The assistant/runtime workflow is:

1. A source document is converted into one proper bundle JSON payload.
2. The backend previews the bundle and validates cross-references, ids, and supported capabilities without writing live runtime data.
3. If the bundle is clean, the user imports it.
4. Import writes validated `AssistantArtifact` drafts only.
5. If a draft is invalid, it stays stored with validation errors.
6. If the invalid reason is an unsupported renderer family, the system may also create a `capability_request` through the low-level path.
7. A user explicitly activates a validated artifact.
8. Activation compiles the artifact into live runtime records.
9. Today reads only the live runtime layer, never raw drafts.

Two important rules follow from this:

- drafts are first-class but inert
- activation is the only path into live behavior

The app does not ingest arbitrary markdown directly. That conversion step happens before preview/import.

## Today Resolution Model

Today is resolved in this order:

1. Load active routines.
2. Filter them by date range and cadence.
3. Resolve which assignments match the selected date.
4. Materialize scheduled cards.
5. Apply date-specific schedule exceptions, if any were authored through routine management.
6. Apply logs.
7. Group the result into slots for the UI.

This means Today is a read-time projection, not a write-time snapshot.

That decision carries an assumption:

We expect schedule resolution to stay cheap enough to compute on demand.

For the current product shape, that is correct.

## Explicit Assumptions

These assumptions are intentional and should remain true unless we consciously redesign the model.

### Product assumptions

- The health assistant is expected to author structured bundle JSON, not freeform markdown imports.
- Drafts must never go live automatically.
- Ordinary new cards should not require schema changes.
- Experiments and programs should consume this runtime later instead of bypassing it.

### Data assumptions

- Card templates are the smallest reusable live unit.
- Routines are schedules, not content repositories.
- Weekly and biweekly cadence are enough for v1.
- Bundle preview/import is the canonical routine-authoring path.
- Date-specific exceptions, if supported, belong in schedule-level exception records, not in Today and not in the base recurring assignment definition.
- Renderer-specific detail belongs in JSON payloads rather than in dedicated columns for every field.

### UX assumptions

- The user acts on Today through cards.
- One-tap completion is the default interaction.
- Detailed logging is optional and renderer-specific.
- Slots such as morning, midday, evening, and anytime are sufficient organizing buckets for now.
- Today is execution-only: completion, partial/skipped state, and feedback are allowed; schedule mutation is not.
- Schedule review should be calendar-first.
- A 2-week schedule view is enough for v1.
- Schedule review must work both by day and by routine.
- Manual routine authoring stays JSON-first for now.
- Source planning docs must be normalized into a deterministic bundle before they reach the app.

### Operational assumptions

- SQLite is adequate for local-first scale and the required relational invariants.
- Activation can safely overwrite compiled runtime records for the same ids.
- Compiled runtime data should be idempotent when activating the same validated artifact repeatedly.
- Assistant artifacts should remain auditable after activation.

## Implicit Assumptions

These were not always stated in code, but the design depends on them.

### The app is an interpreter, not a routine authoring engine

The app should be able to execute and display structured drafts. It should not force every new routine idea through hardcoded product branches.

### A card is both a UI object and a logging contract

We are assuming the unit that is useful to show is also the right unit to log.

That is why the card sits at the center instead of a lower-level exercise atom.

### "Flexible" does not mean arbitrary

We allow flexible payloads, but only inside a controlled renderer family.

This is a deliberate rejection of uncontrolled schema-less design.

### Failure should be visible

If the assistant asks for something unsupported, that should become a visible artifact, not an invisible no-op and not a vague validation message buried in logs.

### Schedules should be composable

We assume multiple routines can overlap and jointly contribute to Today.

That is important because real life does not fit one monolithic plan.

### Schedule mutation and schedule execution are different jobs

We assume the screen used to review or edit schedule structure is not the screen used to execute the day.

That is why Today should log outcomes, while schedule management should own recurrence and any date-specific schedule exceptions.

## What We Deliberately Did Not Model Yet

Several things are intentionally out of scope for v1:

- experiments that analyze routine effects
- the old programs import flow
- arbitrary recurrence rules beyond weekly and biweekly
- arbitrary user-defined renderer families
- precomputed daily instances
- deep cross-card dependency logic
- a rich non-JSON manual routine editor

These are not omissions by accident. They were deferred to protect the core abstraction.

## Failure Modes We Are Trying to Avoid

This design exists largely to avoid these common failures:

### Schema explosion

If every new habit type adds columns, tables, and route branches, the system becomes impossible to extend.

### Hidden programming language in JSON

If payloads become arbitrary UI definitions, the app becomes an unsafe renderer for ad hoc specs and every bug turns into a schema interpretation problem.

### Routine content mixed with scheduling

If routines define both what something is and when it happens, reuse becomes painful and schedule changes require content duplication.

### Today hardcoded to day types

If Today depends on a special taxonomy like hard/easy days, new plan shapes become harder to represent than they should be.

### Today becoming a second schedule editor

If Today can create or restructure work, schedule data becomes split across the recurring routine layer and the day-execution layer.

That destroys the source-of-truth boundary and makes calendar review unreliable.

### Drafts mutating live state directly

If assistant outputs write directly to runtime tables, we lose reviewability, auditability, and safe failure handling.

## How to Extend the Model Safely

When extending the routine runtime, prefer this order of operations:

1. Ask whether the need can be represented as a new `CardTemplateSpec` inside an existing renderer family.
2. If yes, add it as data only.
3. If not, ask whether the interaction is common and stable enough to deserve a new renderer family.
4. Only then add backend validation and frontend rendering support for that new family.
5. Keep experiments, programs, and future planning features downstream of the same runtime instead of creating side systems.

The standard for adding infrastructure should be high.

If a need can be handled as a new card or routine spec, it should stay data.

## Current Open Questions

These are the most important unresolved design questions:

- whether weekly and biweekly cadence are still enough once more experiments return
- whether cards ever need nested sub-card composition or whether renderer payloads are enough
- how experiments should reference cards, routines, or logged occurrences without leaking old abstractions back in
- whether schedule exceptions should remain a first-class schedule-management concept or be deferred entirely until later

## Bottom Line

The system is intentionally card-centered, spec-driven, and renderer-bounded.

That means:

- cards are the reusable behavioral unit
- routines are schedules
- Today is a projection
- Today is for execution and logging, not schedule mutation
- assistant drafts are not live state
- renderer families are the real infrastructure boundary

If we protect those rules, the app can become an interpreter for health-assistant-authored specs instead of a brittle collection of one-off routine features.
