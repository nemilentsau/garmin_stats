# Routine Runtime Implementation Plan

This document is the implementation plan for cleaning up the current routine runtime and schedule UX.

It exists so we do not keep patching around the current mistakes.

The point is to stop, align on the model, implement in controlled phases, and review the output after each phase before moving on.

## Locked Decisions

These are no longer open questions for this implementation pass.

### Product rules

- Today is execution-only.
- Today may log completion, partial/skipped state, notes, and renderer-specific feedback.
- Today must not create new cards or new schedule structure.
- Schedule remains the source of truth for what can appear on Today.

### Schedule rules

- Schedule review must be calendar-first.
- A 2-week view is enough for v1.
- The schedule UI must support two lenses:
  - by day
  - by routine
- The schedule UI must show dated occurrences, not just abstract recurrence metadata.

### Authoring rules

- Manual authoring stays JSON-first for now.
- The canonical authoring/import unit is one proper artifact bundle JSON payload.
- We are not building a rich visual routine editor in this pass.
- The app does not accept arbitrary markdown in-app.
- The creation surface is for bundle preview/import, draft inbox review, and activation, not for solving schedule review.

Canonical flow:

`source doc -> LLM emits proper bundle JSON -> preview -> import drafts -> activate -> Today/Schedule`

### Engineering rules

- The backend must own recurrence resolution.
- The frontend must not implement its own schedule engine.
- Today and Schedule must read from the same resolved schedule model.
- We do not proceed from one phase to the next without review.

## What Is Broken Right Now

This is the current failure state we are fixing.

1. The schedule page is not a schedule.
   It shows counts, cards, and recurrence metadata, but not an actual calendar or dated plan.

2. The only real recurrence resolution lives in Today.
   That means schedule review does not have a proper shared read model.

3. The source-of-truth boundary is still soft.
   Today UI stopped creating cards, but the API shape still supports day-level schedule mutation.

4. The new route split was done before the right read model existed.
   So the UI split is directionally right, but structurally premature.

5. Creation and schedule currently duplicate loading concerns instead of consuming a cleaner domain-specific contract.

## Implementation Strategy

We fix this in four controlled tracks:

1. create one schedule projection model in the backend
2. rebuild schedule around that projection
3. harden the Today boundary so it only logs
4. keep creation narrow and JSON-first

The key principle is:

Do not improve screens independently until the read model is correct.

## Phase 0: Review And Freeze

### Goal

Confirm the exact behaviors we are implementing before touching runtime code again.

### Scope

- restate the locked decisions from this document
- confirm that 2-week view is the only schedule horizon for v1
- confirm that Today is execution-only
- confirm that JSON-first authoring remains acceptable for now

### Deliverables

- accepted implementation plan
- accepted data-schema clarifications

### Review gate

Do not proceed until you confirm this phase in writing.

## Phase 1: Shared Backend Schedule Projection

### Goal

Extract recurrence resolution into a backend-owned schedule projection that both Today and Schedule can consume.

### Scope

- create one backend schedule resolver service
- move cadence/date matching logic out of Today-specific flow into shared logic
- define a projection model for a date range
- expose a schedule API that returns resolved occurrences for a 2-week window
- include enough metadata to support both schedule lenses:
  - date
  - slot
  - routine id and routine name
  - card template id and card name
  - renderer
  - recurrence origin
  - occurrence key
  - any schedule exception marker, if applicable

### Non-goals

- no visual redesign yet
- no creation-flow changes yet
- no rich editor

### Acceptance criteria

- Today no longer owns unique recurrence logic
- schedule projection is deterministic and testable
- frontend does not need to infer biweekly/weekly placement on its own

### Review materials

- sample JSON response for a 2-week range
- test cases for:
  - weekly routine
  - biweekly routine
  - overlapping routines
  - start/end date clipping
  - schedule exception application, if still supported

### Review gate

We review the schedule projection contract before any schedule UI work begins.

## Phase 2: Source-Of-Truth Hardening

### Goal

Make the boundary real, not aspirational.

### Scope

- remove or disable Today API paths that create schedule state
- keep Today write paths only for:
  - completion
  - partial/skipped
  - notes
  - renderer-specific feedback
- decide what to do with schedule exceptions:
  - either keep them as schedule-management-only data
  - or defer them entirely for now

### Decision branch

#### Option A: keep schedule exceptions

- exceptions remain in the backend schema
- they are only created through schedule management flows
- Today only reads them

#### Option B: defer schedule exceptions

- remove add/replace from this pass
- keep only base recurring schedule plus logs
- revisit exceptions later if truly needed

Chosen for the current implementation pass:

- Today does not write schedule exceptions; it still reads persisted ones for backward compatibility
- the Today API keeps only logging writes

### Acceptance criteria

- Today cannot create new cards or date-local plans
- the API contract reflects that restriction
- the frontend client no longer exposes schedule-mutation helpers from Today

### Review materials

- API diff summary
- list of removed or narrowed Today write paths

### Review gate

We review the hardened boundary before rebuilding the final schedule UI.

## Phase 3: Schedule UX Rebuild

### Goal

Replace the current schedule page with an actual schedule.

### Scope

Build `/routines/schedule` around one projection with two lenses.

#### Lens A: By day

- 2-week calendar strip or grid
- each day shows whether it has scheduled cards
- selecting a day opens an agenda for that date
- agenda groups items by slot
- each agenda item shows:
  - card name
  - routine
  - slot
  - renderer/type cue

#### Lens B: By routine

- choose one routine at a time
- show its next dated occurrences within the same 2-week horizon
- make it obvious which dates and slots it occupies
- show routine notes and cadence only as supporting context

### Required UX outcomes

- a user can answer “what happens on this day?”
- a user can answer “where does this routine land over the next two weeks?”
- the page feels like schedule review, not runtime inspection

### Non-goals

- no card library on this page
- no creation inbox on this page
- no generalized analytics or vanity summaries

### Acceptance criteria

- schedule page is obviously calendar-first
- both day and routine review are supported
- dated occurrences are visible without mentally decoding recurrence metadata

### Review materials

- desktop and mobile screenshots
- one example with overlapping routines
- one example with no cards on selected day
- one example of routine lens showing upcoming occurrences

### Review gate

We review screenshots and interaction flow before touching creation.

## Phase 4: Creation Flow Narrowing

### Goal

Keep creation useful but intentionally small.

### Scope

- keep JSON-first authoring
- make bundle preview/import the documented default path
- keep draft inbox and activation
- remove any copy or widgets that imply creation is also schedule review
- make the relationship explicit:
  - creation previews and imports proper bundles
  - creation manages drafts and activation
  - schedule reviews live runtime

### Non-goals

- no rich form builder
- no visual assignment editor
- no calendar editing from creation in this pass

### Acceptance criteria

- creation page is clearly for drafts and activation only
- creation accepts a proper bundle JSON payload instead of arbitrary markdown
- preview validates the whole bundle and writes nothing
- import writes only assistant-artifact drafts
- it does not try to compete with schedule review

### Review materials

- screenshot of creation page
- quick walkthrough of draft -> activate -> inspect in schedule

### Review gate

We confirm creation remains intentionally small and not overbuilt.

## Phase 5: Today Cleanup

### Goal

Make Today a clean execution surface on top of the shared schedule projection.

### Scope

- switch Today to consume the shared resolved schedule model where appropriate
- keep one-tap logging and detail logging
- keep clear copy that schedule problems are fixed in routines, not in Today
- remove any remaining schedule-authoring concepts from Today code or text

### Acceptance criteria

- Today only executes and logs
- Today no longer contains schedule-authoring behaviors
- Today and Schedule agree on what exists for a given date

### Review materials

- side-by-side check:
  - selected day in schedule
  - same day in Today

### Review gate

We verify that the same date produces the same cards in both views.

## Phase 6: Documentation And Stabilization

### Goal

Close the loop so the model and implementation stay aligned.

### Scope

- update README route descriptions if needed
- update architecture docs if new schedule API or resolver module exists
- update `docs/DATA_SCHEMA_DESIGN.md` if any implementation choices changed during review
- document one LLM-facing proper bundle spec for routine import
- add tests for final contracts and regressions

### Acceptance criteria

- docs match behavior
- bundle spec documentation matches the runtime contract
- tests cover the shared schedule projection and Today boundary
- no duplicated recurrence logic remains in frontend code

### Review materials

- final diff summary
- validation results
- screenshot set for schedule and today

## Testing Plan

### Backend

- schedule projection resolves weekly cadence correctly
- schedule projection resolves biweekly cadence correctly
- overlapping routines appear together
- start and end dates clip occurrences correctly
- Today logging still works against occurrence keys produced by projection
- Today cannot create new schedule entries

### Frontend

- schedule page renders a 2-week view with no frontend recurrence math
- switching between by-day and by-routine views works
- selected day agenda matches expected occurrences
- Today matches the same selected day
- creation page still creates and activates drafts successfully

### Visual verification

Must verify in the running app:

- `/routines/schedule` desktop
- `/routines/schedule` mobile
- `/routines/creation` desktop
- `/routines/creation` mobile
- `/today` desktop
- `/today` mobile

## Out Of Scope For This Pass

To avoid building another mess, this pass explicitly does not include:

- rich non-JSON manual editors
- arbitrary markdown ingestion
- arbitrary recurrence rules beyond weekly and biweekly
- experiments integration
- programs reintegration
- deep schedule analytics
- bulk routine editing workflows
- drag-and-drop calendar editing

## Abort Conditions

Stop and review again if any of the following happens:

- recurrence logic starts reappearing in frontend code
- schedule page starts accumulating card-library or draft-inbox concerns again
- Today regains any ability to create schedule structure
- the implementation needs a visual authoring system to finish the pass
- the shared schedule projection cannot support both day and routine lenses cleanly

## Definition Of Done

This cleanup is done only when all of the following are true:

1. Today is execution-only.
2. Schedule is genuinely calendar-first.
3. Schedule can be reviewed by day and by routine.
4. The backend owns recurrence resolution in one place.
5. Creation stays JSON-first and narrow.
6. The same schedule data powers both Schedule and Today.
7. The code is simpler than the current state, not more layered and more duplicated.

## Next Action

Do not implement yet.

Review this document first, decide whether schedule exceptions are in or out for this pass, and then proceed phase by phase with review after each gate.
