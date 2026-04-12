# Check-In TODO

## Current State

- Backend support already exists for daily check-ins at `/api/checkins`.
- The assistant and experiment analysis can read check-ins.
- There is no frontend UI for entering or editing check-ins.

## Why This Matters

- The assistant currently recommends daily check-ins for experiment interpretability.
- Experiments need subjective context to separate intervention effects from confounders.
- Without a UI, check-ins are effectively unavailable to normal use.

## Recommended Placement

Put check-in entry on `/today`, not on `/assistant`, `/experiments`, or a settings/profile page.

Why `/today`:

- check-ins are day-grain operational input
- they belong next to routine completion and daily adherence
- `/today` is the natural "what happened today?" surface

## Recommended First Version

Add a compact `Daily Check-In` card to `/today` with:

- energy
- mood
- motivation
- soreness
- subjective stress
- subjective sleep quality
- subjective workload
- illness flag
- travel flag
- alcohol flag
- optional free-text note

## Scope Rules

- preserve the existing backend API contract
- support today first; past-date editing can be added later if needed
- keep the UI lightweight and fast to complete
- do not bury structured check-in entry inside assistant chat

## Non-Goals

- no assistant-authored check-ins
- no experiment-specific check-in form
- no large journaling UI in phase 1

## Follow-Up

When this is picked up, turn it into a short design/spec before implementation.
