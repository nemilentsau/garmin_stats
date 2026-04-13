# Assistant Cross-Thread Prior Evidence Gating Plan

Date: 2026-04-12

Spec: `docs/superpowers/specs/2026-04-12-assistant-cross-thread-prior-evidence-gating-design.md`

## Goal

Stop ambient cross-thread evidence bleed in the assistant while preserving useful continuity for same-entity and same-intent-family questions.

## Tasks

1. Extend assistant routing/evidence helpers with:
   - explicit recall-language detection
   - intent-family adjacency rules
   - exact entity-overlap matching helpers
2. Replace recency-only `prior_evidence` selection with relevance-gated selection in `backend/app/domains/assistant/application/evidence.py`.
3. Update assistant retrieval tests for:
   - unrelated-family exclusion
   - same-entity inclusion
   - adjacent-family inclusion
   - explicit recall override
4. Run backend verification:
   - `cd backend && uv run ruff check`
   - `cd backend && uv run pyright app/ tests/`
   - `cd backend && uv run pytest tests/ -v`

## Acceptance Criteria

- Fresh threads do not inherit unrelated evidence bundles by recency alone.
- Same-entity experiment queries can still recall relevant prior evidence across threads.
- Same-intent-family fallback remains bounded and deterministic.
- No backend API or stream contract changes.
