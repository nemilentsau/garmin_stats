"""Stable policy prompts for coach model jobs."""

from app.domains.coach.contracts import JobKind

_COMMON = """Read evidence-capabilities.md, brief.md, journal/recent.md, journal/index.md,
plan.md, recovery.md, runs/digest.md, then question.md and transcript.md when present.
The 20-run digest is a menu and chronology, not a selector: open on-demand run files when
needed. Cite every relied-on artifact using typed refs. Do not claim unavailable estimators
or causal conclusions. Any plan adjustment is advisory, never an automatic prescription.
Use semantic journal/brief memory for decisions, conclusions, unresolved hypotheses, and
what to compare next; do not copy telemetry tables or numeric run summaries into memory.
Budgets: review/answer <= 12,000 characters; journal <= 1,600; brief <= 6,000.
"""


def review_prompt(kind: JobKind) -> str:
    action = "Review the current run" if kind == "review_run" else "Review the missed run"
    return f"{_COMMON}\n{action} and return only the required structured output."


def chat_prompt(*, resumed: bool) -> str:
    refresh = ""
    if resumed:
        refresh = (
            "Workspace files were refreshed after your previous turn. Re-read the required "
            "files before answering; do not rely on remembered file contents.\n"
        )
    return f"{_COMMON}\n{refresh}Answer the latest user message in the required structure."


def distill_prompt() -> str:
    return (
        f"{_COMMON}\nDistill the complete transcript into durable semantic memory and return "
        "only the required structure."
    )
