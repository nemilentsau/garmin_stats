"""Versioned semantic-memory helpers for Coach workspaces and persistence."""

from app.domains.coach.contracts import JournalEntry, RunJournalSummary

CURRENT_MEMORY_POLICY_VERSION = 2


def active_journal_entries(
    entries: list[JournalEntry],
    *,
    policy_version: int = CURRENT_MEMORY_POLICY_VERSION,
) -> list[JournalEntry]:
    """Return current-policy entries that have not been superseded."""
    matching = [entry for entry in entries if entry.policy_version == policy_version]
    superseded = {
        entry.supersedes_id
        for entry in matching
        if entry.supersedes_id is not None
    }
    return [entry for entry in matching if entry.id not in superseded]


def render_run_journal(summary: RunJournalSummary) -> str:
    """Render bounded interpretation without duplicating run telemetry."""
    uncertainties = summary.decision_relevant_uncertainties or ["None."]
    triggers = summary.follow_up_triggers or ["No follow-up trigger."]
    refs = [f"- {ref.kind}: {ref.value}" for ref in summary.refs]
    return "\n".join(
        [
            f"Purpose: {summary.purpose}",
            f"Outcome: {summary.outcome.replace('_', ' ')}",
            f"Takeaway: {summary.takeaway}",
            "Decision-relevant uncertainty:",
            *[f"- {item}" for item in uncertainties],
            "Follow-up triggers:",
            *[f"- {item}" for item in triggers],
            "Comparison tags: " + ", ".join(summary.comparison_tags),
            "References:",
            *refs,
        ]
    )
