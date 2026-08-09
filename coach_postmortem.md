# Coach Postmortem

**Date of incident:** 2026-07-28 day debrief (review `98f74dd4`, job `14a736f3`)
**Written:** 2026-08-02
**Status:** draft — this document is the shared understanding the redesign must be built on. If anything here is wrong, the redesign will be wrong.

---

## 1. The incident

The athlete had a hectic day and adapted: no morning slot, ran midday, stacked strength
immediately after the run, and swapped push for legs because their legs were trashed. The
run felt terrible — heat, humidity, probably no food. They wrote exactly that, in plain
language, into the app:

> "The day was hectic. Didn't have time in the morning. Had to run during the day and
> stack strength training afterwards. So switched to push from legs because my legs were
> very tired. I felt like shit during the run. Heat and humidity and I think lack of food.
> Didn't have time to eat."

Then they requested a day debrief. The coach's review came back asking what the strength
session contained and whether **tomorrow's Push A** should be moved — as if the athlete
had never said push was already done. The athlete's reasonable reading: *did it even read
what I wrote?*

## 2. What the system actually did

Forensics from the persisted workspace and Codex log:

- The reflection **was** in the coach's context, three times — twice in `plan.md` and
  once in the run summary's "Training association → Notes" line.
- The model **did read it**. Its output says: *"Pending clarification, treat Push A as
  already satisfied…"* — it provisionally believed the athlete.
- But the structured evidence handed to it as ground truth said the opposite:

  ```
  2026-07-28  Legs 1 — Barbell Back Squat   status: completed   capture: none   notes: none
  2026-07-29  Push A — Upper Chest + Delts  status: pending
  ```

- Faced with a "completed" Legs card containing zero actual evidence and a prose note on
  a *different* card contradicting it, the model hedged and asked its clarifying
  questions — including the one about tomorrow's Push A that made the athlete feel unheard.

So the model behaved about as well as its inputs allowed. **The failure is the system that
constructed those inputs.** That is what this postmortem is about.

## 3. Root cause, in layers

### 3.1 Surface: the capture UX forced the athlete to falsify the record

There was no way to record what actually happened. The athlete did a push session; the
board offered only a "Legs 1" card with variants `full / reduced / skip`. To mark strength
done at all, they had to tap **complete on a card labeled Legs** — a statement both they
and the system knew was false — and then put the truth in the only free-text slot
available, a notes field on the *run* card.

The system made the athlete lie to it in structured form and tell the truth in prose,
then trusted the structure over the truth.

### 3.2 Middle: the athlete's account has no home

There is no day-level place to say what happened. Free text exists only as per-card
`notes` — an annotation *on the plan's objects*. The athlete's account of their day must
be shredded across whichever cards happen to exist, in whatever vocabulary the plan
defined. A `journal` domain with real note/check-in tables exists in the backend and is
dead — no frontend surface ever calls it.

Structurally, the athlete is not a speaker in this system. They are a form-filler
annotating a schedule.

### 3.3 Root: the evidence hierarchy is inverted

The coach is architected as a **plan-review engine**: its workspace is built from
`plan.md` (the schedule with card statuses dumped as JSON — presented as fact), the
telemetry digest, and recovery data. The prompt says strength cards should be coached
"from their logs and the plan." A button triggers it; the athlete's words enter only
incidentally, if they happen to sit in some card's notes field.

That is an inverted epistemology. Ranked by actual authority about what the athlete did
and how it felt:

1. **The athlete's own words** — direct testimony. The highest-authority evidence that
   exists, full stop.
2. **Watch telemetry** — sensors. Objective corroboration of what the body did.
3. **The plan** — a statement of *intention*, written before the day happened. It is
   never evidence about what occurred.
4. **UI toggle state** — not evidence at all. A "completed" flag is testimony laundered
   through a constrained form into something that *looks* like a fact. It carries less
   information than the athlete's words (it can only say what the form allowed) while
   being presented to the coach as harder truth.

The current system feeds the coach layer 3 and 4 as ground truth and layer 1 as an
ancillary string. The incident was not an edge case; it was this inversion expressing
itself the first time real life diverged from the form.

The written intent was right — `docs/reference/coach.md` says the coach is "in dialogue
with a self-aware athlete, not a compliance auditor." The architecture contradicts the
intent: outcome enums per card, compliance-shaped vocabulary, plan-state-as-fact, button
trigger, no channel for the athlete to actually be in dialogue. The prose aspiration
never had structural support.

## 4. Why every proposed fix was a crutch

Three fixes were proposed after the initial diagnosis. All three keep the inverted
hierarchy and add reconciliation machinery on top:

- **Cross-card substitution mechanism** ("executed as Push A") — teaches the form more
  vocabulary so the athlete can pre-translate their life into the plan's terms. The
  athlete becomes a better data-entry clerk. Next divergence outside the new vocabulary
  ("did 30 min of hotel-room work, sort of push-ish") breaks it again. The form can never
  enumerate life.
- **Day-level reflection field wired into the workspace** — gives the words a home but
  still as *one more input* to a plan-centric review. The plan JSON still sits there
  claiming to be fact; the contradiction class survives.
- **Prompt rule "notes win over card state"** — asks the model to resolve, case by case,
  a contradiction the system itself manufactures. Patching the reader instead of the
  writer.

Each is a translation layer between what the athlete said and what the system considers
real. The athlete's verdict — that these are crutches for a fundamentally broken
mechanism — is correct. A system whose primary input is the athlete's speech needs no
reconciliation layer, because there is nothing to reconcile against.

## 5. The redesign conversation repeated the same error

When asked for a complete redesign, the brainstorming question offered options like
"delete the capture UI" and "coach derives the structured record from your words." The
second option implied parsing free text into structured log mutations — a brittle
extraction pipeline that would fail exactly the way the forms fail, one layer later. Both
options still treated *the structured record* as the object of design: the question was
"what happens to the record?" when the principle under discussion was that the record —
as a source of truth about what happened — should not exist.

That is the same inversion, reproduced in the design process itself: reaching for
mechanism-space ("how do we keep structure consistent with speech?") instead of
accepting the premise ("speech is the record; nothing needs to be kept consistent").

There is also a process lesson: the question was asked because the process says to ask
questions, not because it tested a genuine unknown. A question whose every option embeds
the rejected assumption is worse than no question.

## 6. What "feedback-first" actually means

The principle, stated so it can't be re-diluted:

1. **The athlete speaking is the only trigger.** No feedback → no coach run. No buttons
   that summon a review of silence. The coach never has anything to say about a day the
   athlete didn't tell it about — because without the athlete's account it is missing the
   highest-authority evidence and anything it produced would be plan-auditing.
2. **The words are the record.** The athlete's message is stored verbatim, permanently,
   as the primary account of what happened. It is never parsed, extracted, classified,
   or translated into structure. No regex, no LLM extraction into card mutations,
   nothing. The whole point of a language-model coach is that it reads language
   natively; converting language into structs so software can pretend to read it is the
   pathology this redesign removes.
3. **Telemetry corroborates; it never contradicts.** Watch data is sensor truth about
   the body — HR, pace, laps. The coach uses it to add what the athlete *cannot* feel
   (drift, decoupling, comparisons to history) to what the athlete *told* it. It has no
   standing to dispute the athlete's account of intent, context, or feel.
4. **The plan is intention, not truth.** It answers "what was I trying to do this
   block?" — context for coaching, never a source of claims about what happened.
   Deviation from plan is information the athlete reports, not a violation the system
   detects.
5. **No pseudo-facts.** Any UI element that converts the athlete's testimony into a
   structured claim presented as fact ("completed", a status enum, an RPE typed into a
   box that becomes a database truth) manufactures the contradiction class this incident
   exemplified. Whatever the athlete wants to convey — including "RPE 8" — belongs in
   their words, where it keeps its author and its context.

Corollary, answering the question that was asked in anger: **nothing gets deleted "based
on feedback."** Feedback never mutates anything. Cards, plans, logs are not downstream of
speech-parsing. Feedback is stored, and the coach responds to it. That's the entire
data flow.

## 7. What this implies (scope for the redesign — principles, not the design)

- The coach's sole entry point is a conversation: the athlete writes; the coach responds
  with full evidence (their words first, telemetry, history, plan-as-intention)
  assembled around the message.
- Day/week/run "reviews" as button-triggered artifacts with outcome/confidence enums
  are gone. A "review" is what the coach's reply *is* when the athlete recounts a day.
- The per-card capture layer (complete toggles, RPE boxes, card notes) loses its role as
  the record of what happened. Its exact fate — full deletion vs. anything retained for
  non-coach purposes — is a redesign decision, but nothing it produces may ever again be
  presented to the coach as ground truth about the athlete's actions.
- Salvageable and worth keeping: the evidence-workspace machinery (digest, run
  summaries/plots, recovery), the memory layers (journal, brief), the durable job queue,
  and the hermetic Codex runner. They are sound infrastructure pointed at the wrong
  trigger and the wrong primary input.
- The compliance-shaped review schema (outcomes, per-card judgment) does not survive.
  Measurement assessments (LTHR validity gates etc.) are the one place hard structure is
  legitimate — they are about *sensor protocols*, not about the athlete's conduct — and
  need a deliberate decision about where they live in a conversation-first coach.

## 8. Process lessons (for the assistant, recorded so they stick)

1. **Diagnose the writer, not the reader.** The first diagnosis correctly found the
   contradiction but then proposed three patches to the consumer of bad data instead of
   questioning the producer.
2. **When the user states a principle, test the design against the principle — not the
   principle against the existing design.** All three fixes and the failed brainstorming
   question tried to preserve existing structure under a principle that abolishes it.
3. **A clarifying question must test a real unknown.** If every offered option embeds an
   assumption the user already rejected, the question is process theater and actively
   erodes trust.
