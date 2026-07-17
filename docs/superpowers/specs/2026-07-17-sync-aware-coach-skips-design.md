# Sync-Aware Coach Skip Reviews

## Problem

Coach currently treats every scheduled running card from a past local date as a missed run whenever no activity is visible in the local database. Startup reconciliation and the five-minute worker can therefore enqueue a skip review before Garmin activity sync has checked that date. A later sync then creates the real run review, leaving two reviews for one training occurrence.

## Required behavior

- A past scheduled run is eligible for a skip review only after Garmin activity sync has completely checked that date.
- A date is covered only when its activity listing succeeds and every listed activity is either already stored or is downloaded and stored successfully. Partial or failed sweeps must not prove absence.
- Startup ingest alone does not establish coverage because it cannot prove Garmin Connect was checked.
- Run reviews remain eligible immediately when an ingested run exists; they do not depend on coverage.
- If a run later appears for an occurrence that already has a skip review, the run review becomes canonical and the skip is durably marked as superseded.
- Superseded skips remain in SQLite for audit but are omitted from review history and from semantic measurement lookup.
- Reconciliation remains idempotent. Re-running it with unchanged evidence creates no additional reviews or jobs and repairs existing run/skip conflicts.

## Architecture

`garmin_sync` owns a small durable activity-coverage table keyed by local date. The activity sweep records coverage only after a fully successful per-date pass and removes or withholds coverage when that pass is incomplete. It exposes a narrow read method that bootstrap injects into `CoachJobs`; Coach does not import sync infrastructure.

`CoachJobs._candidates` consults that injected coverage reader only before emitting a skip candidate. Run candidate discovery is unchanged.

When the Coach repository enqueues or rediscovers a run review with a date and occurrence key, it marks matching skip reviews with `superseded_by_review_id`. Completion of an already-running skip job preserves that marker. Review listing and latest-measurement queries exclude superseded reviews.

## Failure handling

- Activity-listing, download, payload, or storage failure leaves the date uncovered.
- A later successful sync replaces the incomplete state with covered state.
- Coverage writes occur independently per date so one failed date does not invalidate successful dates in the same sweep.
- Coach reconciliation failures remain isolated from the reported Garmin sync result, as today.

## Verification

Tests will cover:

- unsynced past dates do not enqueue skips;
- fully covered past dates do enqueue skips;
- partial/failed activity sweeps do not record coverage;
- a later successful sweep records coverage;
- a late run supersedes the prior skip and only the run appears in review history;
- superseded skips cannot become the latest measurement assessment;
- repeated sync and reconciliation are idempotent;
- the real local data tree passes a read-only startup/reconciliation smoke check.

