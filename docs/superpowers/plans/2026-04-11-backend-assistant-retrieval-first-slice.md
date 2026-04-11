# Backend Assistant Retrieval-First Slice Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the current assistant internals with a retrieval-first, backend-owned continuity layer while keeping the existing `/api/assistant` HTTP and NDJSON stream contract stable for the frontend.

**Architecture:** This slice is an API-stable internal rewrite, not a compatibility-wrapper migration. The new owner is `backend/app/domains/assistant/`, with deterministic query routing, entity resolution, targeted retrieval, persisted evidence bundles, global memory, and a stateless generation path that does not depend on Claude session resume.

**Tech Stack:** Python 3.14, FastAPI, Pydantic v2, SQLite, pytest, uv, ruff, pyright, Claude Code runtime

---

## Scope Note

This plan supersedes [2026-04-10-backend-assistant-slice.md](/Users/andreinemilentsau/Projects/garmin_stats/docs/superpowers/plans/2026-04-10-backend-assistant-slice.md).

This slice covers:

1. `/api/assistant/threads`
2. `/api/assistant/threads/{thread_id}`
3. `/api/assistant/threads/{thread_id}/messages`
4. deterministic intent routing
5. deterministic entity resolution
6. targeted evidence retrieval
7. persisted evidence bundles and global memory
8. stateless grounded generation
9. follow-up continuity without Claude session resume

This slice does not cover:

- assistant artifact or bundle APIs
- routine or experiment authoring actions
- a full planner loop
- frontend UX changes

## File Map

### Create

- `backend/app/domains/assistant/__init__.py`
  Domain package marker.

- `backend/app/domains/assistant/api/__init__.py`
  API package marker.

- `backend/app/domains/assistant/api/threads.py`
  Stable `/api/assistant` HTTP routes and NDJSON stream boundary.

- `backend/app/domains/assistant/application/__init__.py`
  Application package marker.

- `backend/app/domains/assistant/application/types.py`
  Internal assistant domain/application models for route decisions, resolved entities, evidence bundles, and memory records.

- `backend/app/domains/assistant/application/ports.py`
  Protocols for conversation persistence, read-model access, and generation runtime.

- `backend/app/domains/assistant/application/threads.py`
  Thread and message catalog use cases.

- `backend/app/domains/assistant/application/router.py`
  Deterministic intent routing with confidence scoring.

- `backend/app/domains/assistant/application/entity_resolution.py`
  Deterministic entity matching and ambiguity handling.

- `backend/app/domains/assistant/application/retrieval.py`
  Domain retrievers and retrieval coordinator.

- `backend/app/domains/assistant/application/evidence.py`
  Evidence bundle construction helpers.

- `backend/app/domains/assistant/application/chat.py`
  End-to-end orchestration for saving the user message, retrieving evidence, streaming deterministic first delta, calling the runtime, and persisting the answer.

- `backend/app/domains/assistant/infra/__init__.py`
  Infrastructure package marker.

- `backend/app/domains/assistant/infra/sqlite_repository.py`
  SQLite-backed implementation of conversation persistence and read-model access.

- `backend/app/domains/assistant/infra/runtime.py`
  Stateless Claude Code runtime adapter that reads persisted evidence and thread/memory files instead of relying on `--resume`.

- `backend/tests/test_assistant_threads_application.py`
  Thread and message catalog behavior tests.

- `backend/tests/test_assistant_router_application.py`
  Intent routing behavior tests.

- `backend/tests/test_assistant_entity_resolution.py`
  Entity resolution tests.

- `backend/tests/test_assistant_retrieval.py`
  Evidence retrieval tests.

- `backend/tests/test_assistant_chat_application.py`
  Follow-up continuity, stream orchestration, and grounded reply tests.

- `backend/tests/test_architecture_assistant_boundaries.py`
  Assistant layering and ownership guard tests.

### Modify

- `backend/app/bootstrap/container.py`
  Wire assistant dependencies from the new domain.

- `backend/app/bootstrap/routing.py`
  Mount the new domain-local assistant router directly.

- `backend/app/infra/database.py`
  Add assistant evidence and global memory tables plus CRUD helpers.

- `backend/tests/test_database.py`
  Round-trip tests for assistant evidence and memory persistence.

- `backend/tests/test_phase2_routes.py`
  Preserve public `/api/assistant` contract coverage while the owner moves.

- `backend/tests/test_assistant_runtime.py`
  Repoint runtime tests to the stateless runtime adapter and remove resume-dependent assumptions.

- `docs/ARCHITECTURE.md`
  Update the current-state assistant architecture description after the slice lands.

### Delete

- `backend/app/routers/assistant.py`
  Old flat route owner should be removed after imports move to `domains/assistant/api/threads.py`.

- `backend/app/services/assistant.py`
  Old flat orchestration module should be removed after `domains/assistant/application/chat.py` and `threads.py` own behavior.

- `backend/app/services/assistant_context.py`
  Generic snapshot builder should be removed after targeted retrieval replaces it.

- `backend/app/services/assistant_runtime.py`
  Old resume-dependent runtime wrapper should be removed after `domains/assistant/infra/runtime.py` lands.

- `backend/tests/test_assistant_service.py`
  Old flat-service orchestration tests should be replaced by application-level chat tests.

- `backend/tests/test_assistant_context.py`
  Generic snapshot tests should be replaced by retrieval and evidence tests.

## Task 1: Lock The Public Contract And The Broken Follow-Up Case

**Files:**
- Create: `backend/tests/test_assistant_chat_application.py`
- Modify: `backend/tests/test_phase2_routes.py`

- [ ] **Step 1: Write a failing continuity test for a stale external session**

Add a test that proves follow-ups must work even when the thread has a stale `claude_session_id`.

```python
async def test_follow_up_works_without_claude_resume(monkeypatch):
    repo = _FakeConversationStore.with_thread(
        thread_id="thread-1",
        claude_session_id="stale-session-id",
    )
    runtime = _FakeRuntime(deltas=["You should keep going."])

    lines = await _collect(
        stream_reply(
            repo=repo,
            read_store=_FakeReadStore.for_experiment_review(),
            runtime=runtime,
            thread_id="thread-1",
            request=AssistantMessageCreateRequest(
                id="message-2",
                content="Any suggestions for me",
            ),
        )
    )

    payloads = [json.loads(line) for line in lines]
    assert payloads[-1]["type"] == "done"
    assert "keep going" in payloads[-1]["message"]["content_markdown"].lower()
```

- [ ] **Step 2: Run the continuity test to verify it fails for the right reason**

Run:

```bash
cd backend && uv run pytest tests/test_assistant_chat_application.py::test_follow_up_works_without_claude_resume -v
```

Expected: fail because the new chat orchestration and stateless runtime path do not exist yet.

- [ ] **Step 3: Write a failing route-contract test that preserves NDJSON event shape**

In `backend/tests/test_phase2_routes.py`, add a route-level test that asserts the stream still emits `delta` and `done` payloads with the current field names.

```python
def test_post_thread_message_keeps_ndjson_contract(monkeypatch):
    async def fake_stream(*_args, **_kwargs):
        yield json.dumps({"type": "delta", "text": "hello"}) + "\n"
        yield json.dumps(
            {
                "type": "done",
                "message": {"id": "assistant-1", "thread_id": "thread-1", "role": "assistant", "content_markdown": "hello"},
                "session_id": None,
                "snapshot_id": "evidence-1",
                "run_id": "run-1",
            }
        ) + "\n"
```

- [ ] **Step 4: Run the route-contract test to verify it fails because the new owner is missing**

Run:

```bash
cd backend && uv run pytest tests/test_phase2_routes.py::TestAssistantRoutes::test_post_thread_message_keeps_ndjson_contract -v
```

Expected: fail because the old route owner is still mounted and the new domain-local route is not in place.

- [ ] **Step 5: Commit the red tests**

```bash
git add backend/tests/test_assistant_chat_application.py backend/tests/test_phase2_routes.py
git commit -m "test: lock assistant continuity and stream contract"
```

## Task 2: Persist Evidence Bundles And Global Memory

**Files:**
- Create: `backend/app/domains/assistant/application/types.py`
- Modify: `backend/app/infra/database.py`
- Modify: `backend/tests/test_database.py`

- [ ] **Step 1: Write failing round-trip tests for assistant evidence and memory records**

Add database tests for new assistant-owned persistence types.

```python
def test_assistant_evidence_bundle_round_trips():
    bundle = AssistantEvidenceBundle(
        id="evidence-1",
        thread_id="thread-1",
        user_message_id="message-1",
        intent="experiment_review",
        entities=[AssistantResolvedEntity(kind="experiment", entity_id="exp-1", label="Meditation → HRV", score=0.98)],
        items=[AssistantEvidenceItem(kind="analysis", source="experiment_analysis", entity_id="exp-1", payload_json={"adherence_rate": 0.5})],
        gaps=[],
    )

    db.save_assistant_evidence_bundle(bundle)

    loaded = db.load_assistant_evidence_bundles(thread_id="thread-1")
    assert loaded[0].intent == "experiment_review"
    assert loaded[0].entities[0].entity_id == "exp-1"


def test_assistant_memory_record_round_trips():
    record = AssistantMemoryRecord(
        id="memory-1",
        kind="entity_alias",
        entity_id="exp-1",
        alias_text="meditation experiment",
        payload_json={"source": "resolver"},
    )

    db.save_assistant_memory_record(record)

    loaded = db.load_assistant_memory_records(kind="entity_alias")
    assert loaded[0].alias_text == "meditation experiment"
```

- [ ] **Step 2: Run the new database tests to verify they fail**

Run:

```bash
cd backend && uv run pytest tests/test_database.py -k "assistant_evidence_bundle_round_trips or assistant_memory_record_round_trips" -v
```

Expected: fail because the tables, helpers, and assistant internal types do not exist yet.

- [ ] **Step 3: Define the assistant internal persistence models**

Create `backend/app/domains/assistant/application/types.py` with explicit internal types.

```python
AssistantIntent = Literal[
    "experiment_review",
    "routine_adherence",
    "recovery_briefing",
    "open_ended_coaching",
]


class AssistantResolvedEntity(_DefaultsRequired):
    kind: Literal["experiment", "routine", "metric", "memory"]
    entity_id: str
    label: str
    score: float


class AssistantEvidenceItem(_DefaultsRequired):
    kind: str
    source: str
    entity_id: str | None = None
    payload_json: dict[str, object] = {}


class AssistantEvidenceBundle(_DefaultsRequired):
    id: str
    thread_id: str
    user_message_id: str
    intent: AssistantIntent
    entities: list[AssistantResolvedEntity] = []
    items: list[AssistantEvidenceItem] = []
    gaps: list[str] = []
    created_at: str | None = None


class AssistantMemoryRecord(_DefaultsRequired):
    id: str
    kind: Literal["entity_alias", "evidence_summary"]
    entity_id: str | None = None
    alias_text: str | None = None
    payload_json: dict[str, object] = {}
    created_at: str | None = None
```

- [ ] **Step 4: Add minimal database helpers and schema**

Extend `backend/app/infra/database.py` with two JSON-backed tables and CRUD helpers.

```python
"assistant_evidence_bundles",
"assistant_memory_records",
```

```python
def save_assistant_evidence_bundle(bundle: AssistantEvidenceBundle) -> None:
    _save_json_record(
        "assistant_evidence_bundles",
        bundle.id,
        bundle.model_dump_json(),
        extra_columns={
            "thread_id": bundle.thread_id,
            "user_message_id": bundle.user_message_id,
            "intent": bundle.intent,
        },
    )


def load_assistant_evidence_bundles(
    thread_id: str | None = None,
    *,
    last_n: int | None = None,
) -> list[AssistantEvidenceBundle]:
    where_sql = "thread_id = ?" if thread_id is not None else ""
    params = (thread_id,) if thread_id is not None else ()
    return _load_json_records(
        "assistant_evidence_bundles",
        AssistantEvidenceBundle,
        where_sql=where_sql,
        params=params,
        order_by="created_at, id",
        last_n=last_n,
    )
```

- [ ] **Step 5: Run the new database tests and make them pass**

Run:

```bash
cd backend && uv run pytest tests/test_database.py -k "assistant_evidence_bundle_round_trips or assistant_memory_record_round_trips" -v
```

Expected: both PASS.

- [ ] **Step 6: Commit the persistence layer**

```bash
git add backend/app/domains/assistant/application/types.py backend/app/infra/database.py backend/tests/test_database.py
git commit -m "feat: persist assistant evidence bundles and memory records"
```

## Task 3: Move Thread And Message Catalog Into `domains/assistant`

**Files:**
- Create: `backend/app/domains/assistant/application/ports.py`
- Create: `backend/app/domains/assistant/application/threads.py`
- Create: `backend/app/domains/assistant/infra/sqlite_repository.py`
- Create: `backend/tests/test_assistant_threads_application.py`
- Modify: `backend/app/bootstrap/container.py`

- [ ] **Step 1: Write failing tests for thread ordering and message listing**

Create `backend/tests/test_assistant_threads_application.py`.

```python
def test_list_threads_orders_by_last_message_desc():
    repo = _FakeConversationStore(
        threads=[
            AssistantThread(id="older", title="Older", last_message_at="2026-04-10T10:00:00+00:00"),
            AssistantThread(id="newer", title="Newer", last_message_at="2026-04-11T10:00:00+00:00"),
        ]
    )

    response = list_threads(repo)

    assert [thread.id for thread in response.threads] == ["newer", "older"]


def test_list_messages_raises_for_missing_thread():
    repo = _FakeConversationStore(threads=[], messages=[])

    with pytest.raises(LookupError, match="Assistant thread missing not found"):
        list_messages(repo, "missing")
```

- [ ] **Step 2: Run the new thread tests to verify they fail**

Run:

```bash
cd backend && uv run pytest tests/test_assistant_threads_application.py -v
```

Expected: fail because the new application thread use cases and ports do not exist yet.

- [ ] **Step 3: Define the assistant ports and repository adapter**

Create `backend/app/domains/assistant/application/ports.py`.

```python
class AssistantConversationStore(Protocol):
    def list_threads(self) -> list[AssistantThread]: ...
    def get_thread(self, thread_id: str) -> AssistantThread | None: ...
    def save_thread(self, thread: AssistantThread) -> None: ...
    def list_messages(self, thread_id: str) -> list[AssistantMessage]: ...
    def save_message(self, message: AssistantMessage) -> None: ...
    def save_run(self, run: AssistantRun) -> None: ...
    def save_evidence_bundle(self, bundle: AssistantEvidenceBundle) -> None: ...
    def list_evidence_bundles(self, thread_id: str, *, last_n: int | None = None) -> list[AssistantEvidenceBundle]: ...
    def save_memory_record(self, record: AssistantMemoryRecord) -> None: ...
    def list_memory_records(self, *, kind: str | None = None, last_n: int | None = None) -> list[AssistantMemoryRecord]: ...


class AssistantReadModelStore(Protocol):
    def list_active_experiments(self) -> list[Experiment]: ...
    def get_experiment_analysis(self, experiment_id: str) -> ExperimentAnalysis | None: ...
    def list_experiment_exposures(self, experiment_id: str) -> list[ExperimentExposure]: ...
    def list_active_routines(self) -> list[RoutineSchedule]: ...
    def list_routine_assignments(self, routine_id: str) -> list[RoutineAssignment]: ...
    def list_card_logs_range(self, *, start_date: str, end_date: str) -> list[CardLog]: ...
    def list_recent_metrics(self, *, last_n: int) -> list[DailyMetric]: ...
    def list_recent_checkins(self, *, last_n: int) -> list[DailyCheckIn]: ...
    def list_recent_notes(self, *, last_n: int) -> list[Note]: ...
    def get_profile(self) -> UserProfile | None: ...
```

- [ ] **Step 4: Implement the thread catalog use cases and SQLite adapter**

Create `backend/app/domains/assistant/application/threads.py`.

```python
def list_threads(repo: AssistantConversationStore) -> AssistantThreadsResponse:
    threads = sorted(
        repo.list_threads(),
        key=lambda thread: thread.last_message_at or thread.created_at or "",
        reverse=True,
    )
    return AssistantThreadsResponse(threads=threads)


def list_messages(repo: AssistantConversationStore, thread_id: str) -> AssistantMessagesResponse:
    thread = repo.get_thread(thread_id)
    if thread is None:
        raise LookupError(f"Assistant thread {thread_id} not found")
    return AssistantMessagesResponse(messages=repo.list_messages(thread_id))
```

- [ ] **Step 5: Wire the repository into the composition root**

Extend `backend/app/bootstrap/container.py`.

```python
from app.domains.assistant.infra.sqlite_repository import SqliteAssistantRepository


@dataclass(frozen=True)
class AppContainer:
    routines_repo: SqliteRoutineRepository = field(default_factory=SqliteRoutineRepository)
    assistant_repo: SqliteAssistantRepository = field(default_factory=SqliteAssistantRepository)
```

- [ ] **Step 6: Run the thread tests and make them pass**

Run:

```bash
cd backend && uv run pytest tests/test_assistant_threads_application.py -v
```

Expected: PASS.

- [ ] **Step 7: Commit the assistant catalog layer**

```bash
git add backend/app/domains/assistant/application/ports.py backend/app/domains/assistant/application/threads.py backend/app/domains/assistant/infra/sqlite_repository.py backend/app/bootstrap/container.py backend/tests/test_assistant_threads_application.py
git commit -m "feat: add assistant conversation repository and thread use cases"
```

## Task 4: Add Deterministic Routing And Entity Resolution

**Files:**
- Create: `backend/app/domains/assistant/application/router.py`
- Create: `backend/app/domains/assistant/application/entity_resolution.py`
- Create: `backend/tests/test_assistant_router_application.py`
- Create: `backend/tests/test_assistant_entity_resolution.py`

- [ ] **Step 1: Write failing routing tests for known assistant intents**

```python
def test_router_classifies_experiment_review_questions():
    decision = route_user_query("How does our meditation experiment look like so far?")
    assert decision.intent == "experiment_review"
    assert decision.confidence >= 0.9


def test_router_classifies_recovery_briefing_questions():
    decision = route_user_query("Give me a quick recovery briefing for today")
    assert decision.intent == "recovery_briefing"
```

- [ ] **Step 2: Write a failing entity-resolution test for the meditation experiment**

```python
def test_entity_resolver_matches_meditation_experiment_to_active_experiment():
    store = _FakeReadStore(
        experiments=[Experiment(id="meditation-hrv-2026-03", name="Meditation → HRV", status="active")]
    )

    resolved = resolve_entities(
        store=store,
        memory=[],
        route=AssistantRouteDecision(intent="experiment_review", confidence=0.95),
        query="How does our meditation experiment look like so far?",
    )

    assert resolved[0].kind == "experiment"
    assert resolved[0].entity_id == "meditation-hrv-2026-03"
```

- [ ] **Step 3: Run the router and resolver tests to verify they fail**

Run:

```bash
cd backend && uv run pytest tests/test_assistant_router_application.py tests/test_assistant_entity_resolution.py -v
```

Expected: fail because the routing and entity-resolution modules do not exist yet.

- [ ] **Step 4: Implement deterministic routing**

Create `backend/app/domains/assistant/application/router.py`.

```python
def route_user_query(query: str) -> AssistantRouteDecision:
    q = query.casefold()
    if "experiment" in q or "so far" in q and "meditation" in q:
        return AssistantRouteDecision(intent="experiment_review", confidence=0.95)
    if "briefing" in q or "recovery" in q or "readiness" in q:
        return AssistantRouteDecision(intent="recovery_briefing", confidence=0.9)
    if "routine" in q or "today" in q or "adherence" in q:
        return AssistantRouteDecision(intent="routine_adherence", confidence=0.85)
    return AssistantRouteDecision(intent="open_ended_coaching", confidence=0.6)
```

- [ ] **Step 5: Implement deterministic entity resolution with ambiguity fallback**

Create `backend/app/domains/assistant/application/entity_resolution.py`.

```python
def resolve_entities(
    *,
    store: AssistantReadModelStore,
    memory: list[AssistantMemoryRecord],
    route: AssistantRouteDecision,
    query: str,
) -> list[AssistantResolvedEntity]:
    candidates: list[AssistantResolvedEntity] = []
    for experiment in store.list_active_experiments():
        score = _token_overlap_score(query, experiment.name)
        if score >= 0.4:
            candidates.append(
                AssistantResolvedEntity(
                    kind="experiment",
                    entity_id=experiment.id,
                    label=experiment.name,
                    score=score,
                )
            )
    candidates.sort(key=lambda item: item.score, reverse=True)
    return candidates[:1]
```

- [ ] **Step 6: Run the router and resolver tests and make them pass**

Run:

```bash
cd backend && uv run pytest tests/test_assistant_router_application.py tests/test_assistant_entity_resolution.py -v
```

Expected: PASS.

- [ ] **Step 7: Commit the routing layer**

```bash
git add backend/app/domains/assistant/application/router.py backend/app/domains/assistant/application/entity_resolution.py backend/tests/test_assistant_router_application.py backend/tests/test_assistant_entity_resolution.py
git commit -m "feat: add assistant query routing and entity resolution"
```

## Task 5: Replace Generic Snapshots With Targeted Retrieval And Evidence Bundles

**Files:**
- Create: `backend/app/domains/assistant/application/retrieval.py`
- Create: `backend/app/domains/assistant/application/evidence.py`
- Create: `backend/tests/test_assistant_retrieval.py`

- [ ] **Step 1: Write a failing experiment-review retrieval test**

```python
def test_experiment_review_retriever_returns_analysis_adherence_and_linked_routine():
    store = _FakeReadStore.for_experiment_review(
        experiment_id="meditation-hrv-2026-03",
        routine_id="two-week-meditation-foundation-routine",
    )
    entities = [
        AssistantResolvedEntity(
            kind="experiment",
            entity_id="meditation-hrv-2026-03",
            label="Meditation → HRV",
            score=0.98,
        )
    ]

    bundle = build_evidence_bundle(
        store=store,
        route=AssistantRouteDecision(intent="experiment_review", confidence=0.95),
        entities=entities,
        thread_id="thread-1",
        user_message_id="message-1",
    )

    kinds = [item.kind for item in bundle.items]
    assert "experiment" in kinds
    assert "analysis" in kinds
    assert "exposures" in kinds
    assert "linked_routine" in kinds
```

- [ ] **Step 2: Run the retrieval test to verify it fails**

Run:

```bash
cd backend && uv run pytest tests/test_assistant_retrieval.py::test_experiment_review_retriever_returns_analysis_adherence_and_linked_routine -v
```

Expected: fail because the retrieval and evidence modules do not exist yet.

- [ ] **Step 3: Implement the evidence bundle builder**

Create `backend/app/domains/assistant/application/evidence.py`.

```python
def make_bundle(
    *,
    thread_id: str,
    user_message_id: str,
    route: AssistantRouteDecision,
    entities: list[AssistantResolvedEntity],
    items: list[AssistantEvidenceItem],
    gaps: list[str],
) -> AssistantEvidenceBundle:
    return AssistantEvidenceBundle(
        id=f"evidence-{uuid4().hex}",
        thread_id=thread_id,
        user_message_id=user_message_id,
        intent=route.intent,
        entities=entities,
        items=items,
        gaps=gaps,
        created_at=now_iso(),
    )
```

- [ ] **Step 4: Implement the experiment-review retriever**

Create `backend/app/domains/assistant/application/retrieval.py`.

```python
def retrieve_experiment_review(
    store: AssistantReadModelStore,
    experiment_id: str,
) -> list[AssistantEvidenceItem]:
    experiment = next(exp for exp in store.list_active_experiments() if exp.id == experiment_id)
    analysis = store.get_experiment_analysis(experiment_id)
    exposures = store.list_experiment_exposures(experiment_id)
    routine = next(
        (routine for routine in store.list_active_routines() if routine.id in experiment.linked_routine_ids),
        None,
    )

    items = [
        AssistantEvidenceItem(kind="experiment", source="experiments", entity_id=experiment.id, payload_json=experiment.model_dump()),
        AssistantEvidenceItem(kind="analysis", source="experiment_analyses", entity_id=experiment.id, payload_json=analysis.model_dump() if analysis else {}),
        AssistantEvidenceItem(kind="exposures", source="experiment_exposures", entity_id=experiment.id, payload_json={"items": [item.model_dump() for item in exposures]}),
    ]
    if routine is not None:
        items.append(
            AssistantEvidenceItem(kind="linked_routine", source="routine_schedules", entity_id=routine.id, payload_json=routine.model_dump())
        )
    return items
```

- [ ] **Step 5: Add cross-thread recall from evidence bundles and alias memory**

Extend `build_evidence_bundle(...)` to include recent evidence and memory records by default.

```python
recent_evidence = store.list_evidence_bundles(thread_id, last_n=3)
memory = store.list_memory_records(last_n=10)
```

```python
items.extend(
    AssistantEvidenceItem(
        kind="prior_evidence",
        source="assistant_evidence_bundles",
        payload_json={"items": [bundle.model_dump() for bundle in recent_evidence]},
    )
    for _ in [0]
    if recent_evidence
)
```

- [ ] **Step 6: Run the retrieval test and make it pass**

Run:

```bash
cd backend && uv run pytest tests/test_assistant_retrieval.py -v
```

Expected: PASS.

- [ ] **Step 7: Commit the retrieval layer**

```bash
git add backend/app/domains/assistant/application/retrieval.py backend/app/domains/assistant/application/evidence.py backend/tests/test_assistant_retrieval.py
git commit -m "feat: add assistant evidence retrieval and bundling"
```

## Task 6: Rewrite Chat Orchestration Around Backend-Owned Continuity

**Files:**
- Create: `backend/app/domains/assistant/application/chat.py`
- Create: `backend/app/domains/assistant/infra/runtime.py`
- Modify: `backend/tests/test_assistant_chat_application.py`
- Modify: `backend/tests/test_assistant_runtime.py`

- [ ] **Step 1: Expand the failing chat tests to cover deterministic first delta and stored evidence**

```python
async def test_stream_reply_emits_fast_grounded_first_delta_before_runtime_tokens():
    repo = _FakeConversationStore.with_thread("thread-1")
    runtime = _FakeRuntime(deltas=["Detailed recommendation."])

    lines = await _collect(
        stream_reply(
            repo=repo,
            read_store=_FakeReadStore.for_experiment_review(),
            runtime=runtime,
            thread_id="thread-1",
            request=AssistantMessageCreateRequest(
                id="message-1",
                content="How does our meditation experiment look like so far?",
            ),
        )
    )

    payloads = [json.loads(line) for line in lines]
    assert payloads[0]["type"] == "delta"
    assert "Meditation" in payloads[0]["text"]
    assert repo.saved_evidence_bundles[0].intent == "experiment_review"
```

- [ ] **Step 2: Add a failing runtime test that ignores stale resume state**

```python
def test_runtime_writes_evidence_and_thread_files_without_resume(monkeypatch, tmp_path):
    runtime = ClaudeCodeRuntime()
    monkeypatch.setattr(runtime_mod, "_WORKSPACE_ROOT", tmp_path)

    workspace = runtime_mod._write_workspace_files(
        evidence_bundle=_sample_bundle(),
        prior_messages=[_sample_message()],
        memory_records=[_sample_memory()],
        prompt="Any suggestions for me?",
    )

    assert (workspace / "evidence.json").exists()
    assert (workspace / "thread_messages.json").exists()
    assert (workspace / "memory.json").exists()
```

- [ ] **Step 3: Run the chat and runtime tests to verify they fail**

Run:

```bash
cd backend && uv run pytest tests/test_assistant_chat_application.py tests/test_assistant_runtime.py -v
```

Expected: fail because the new chat orchestration and stateless runtime do not exist yet.

- [ ] **Step 4: Implement stateless runtime file writing and remove resume dependence**

Create `backend/app/domains/assistant/infra/runtime.py`.

```python
def _write_workspace_files(
    *,
    evidence_bundle: AssistantEvidenceBundle,
    prior_messages: list[AssistantMessage],
    memory_records: list[AssistantMemoryRecord],
    prompt: str,
) -> Path:
    workspace = _WORKSPACE_ROOT / evidence_bundle.id
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / "evidence.json").write_text(evidence_bundle.model_dump_json(indent=2), encoding="utf-8")
    (workspace / "thread_messages.json").write_text(json.dumps([message.model_dump() for message in prior_messages], indent=2), encoding="utf-8")
    (workspace / "memory.json").write_text(json.dumps([record.model_dump() for record in memory_records], indent=2), encoding="utf-8")
    (workspace / "task.md").write_text(prompt, encoding="utf-8")
    return workspace
```

```python
cmd = [
    _CLAUDE_CMD,
    "-p",
    prompt,
    "--output-format",
    "stream-json",
    "--verbose",
    "--include-partial-messages",
    "--allowedTools",
    "Read",
    "--model",
    model,
]
```

Do not append `--resume` in this first rewrite.

- [ ] **Step 5: Implement chat orchestration around route -> resolve -> retrieve -> generate**

Create `backend/app/domains/assistant/application/chat.py`.

```python
async def stream_reply(
    *,
    repo: AssistantConversationStore,
    read_store: AssistantReadModelStore,
    runtime: AssistantRuntime,
    thread_id: str,
    request: AssistantMessageCreateRequest,
) -> AsyncIterator[str]:
    thread = get_thread(repo, thread_id)
    user_message = AssistantMessage(
        id=request.id,
        thread_id=thread_id,
        role="user",
        content_markdown=request.content,
        created_at=now_iso(),
    )
    repo.save_message(user_message)

    route = route_user_query(request.content)
    memory = repo.list_memory_records(last_n=10)
    entities = resolve_entities(store=read_store, memory=memory, route=route, query=request.content)
    bundle = build_evidence_bundle(
        store=read_store,
        repo=repo,
        route=route,
        entities=entities,
        thread_id=thread_id,
        user_message_id=user_message.id,
    )
    repo.save_evidence_bundle(bundle)

    first_delta = build_fast_grounded_delta(bundle)
    if first_delta:
        yield json.dumps({"type": "delta", "text": first_delta}) + "\n"

    async for event in runtime.stream_chat(
        evidence_bundle=bundle,
        prior_messages=repo.list_messages(thread_id),
        memory_records=memory,
        user_message=request.content,
        model=thread.model,
    ):
        yield json.dumps(event) + "\n"
```

- [ ] **Step 6: Run the chat and runtime tests and make them pass**

Run:

```bash
cd backend && uv run pytest tests/test_assistant_chat_application.py tests/test_assistant_runtime.py -v
```

Expected: PASS.

- [ ] **Step 7: Commit the chat rewrite**

```bash
git add backend/app/domains/assistant/application/chat.py backend/app/domains/assistant/infra/runtime.py backend/tests/test_assistant_chat_application.py backend/tests/test_assistant_runtime.py
git commit -m "feat: rewrite assistant chat around retrieval-first continuity"
```

## Task 7: Move The HTTP Boundary, Delete Old Internals, And Enforce Ownership

**Files:**
- Create: `backend/app/domains/assistant/api/threads.py`
- Create: `backend/tests/test_architecture_assistant_boundaries.py`
- Modify: `backend/app/bootstrap/routing.py`
- Modify: `backend/tests/test_phase2_routes.py`
- Modify: `docs/ARCHITECTURE.md`
- Delete: `backend/app/routers/assistant.py`
- Delete: `backend/app/services/assistant.py`
- Delete: `backend/app/services/assistant_context.py`
- Delete: `backend/app/services/assistant_runtime.py`
- Delete: `backend/tests/test_assistant_service.py`
- Delete: `backend/tests/test_assistant_context.py`

- [ ] **Step 1: Write failing architecture tests that ban the old ownership model**

```python
def test_assistant_domain_api_does_not_import_flat_service_modules():
    source = Path("backend/app/domains/assistant/api/threads.py").read_text()
    assert "app.services.assistant" not in source
    assert "app.services.assistant_context" not in source
    assert "app.services.assistant_runtime" not in source


def test_bootstrap_routing_mounts_domain_assistant_router_directly():
    source = Path("backend/app/bootstrap/routing.py").read_text()
    assert "from app.domains.assistant.api.threads import router as assistant_router" in source
```

- [ ] **Step 2: Run the architecture tests to verify they fail**

Run:

```bash
cd backend && uv run pytest tests/test_architecture_assistant_boundaries.py -v
```

Expected: fail because the domain-local router does not exist and bootstrap still mounts the old owner.

- [ ] **Step 3: Mount the new domain router and delete the flat assistant modules**

Create `backend/app/domains/assistant/api/threads.py`.

```python
router = APIRouter(prefix="/api/assistant", tags=["assistant"])


@router.get("/threads", response_model=AssistantThreadsResponse)
def get_threads():
    return list_threads(build_container().assistant_repo)


@router.post("/threads/{thread_id}/messages")
async def post_thread_message(thread_id: str, request: AssistantMessageCreateRequest):
    container = build_container()
    return StreamingResponse(
        stream_reply(
            repo=container.assistant_repo,
            read_store=container.assistant_repo,
            runtime=container.assistant_runtime,
            thread_id=thread_id,
            request=request,
        ),
        media_type="application/x-ndjson",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
```

Update `backend/app/bootstrap/routing.py` to import the new router directly, then delete the old flat modules and tests.

- [ ] **Step 4: Update route tests and architecture docs**

In `backend/tests/test_phase2_routes.py`, monkeypatch the new domain-local chat owner instead of the deleted flat service.

```python
monkeypatch.setattr(
    "app.domains.assistant.application.chat.stream_reply",
    fake_stream_reply,
)
```

Update `docs/ARCHITECTURE.md` so the assistant section describes:

- `domains/assistant/` as the owner
- retrieval-first evidence bundling
- backend-owned continuity
- no dependence on generic snapshots or external resume state

- [ ] **Step 5: Run the route and architecture tests and make them pass**

Run:

```bash
cd backend && uv run pytest tests/test_phase2_routes.py tests/test_architecture_assistant_boundaries.py -v
```

Expected: PASS.

- [ ] **Step 6: Run full verification**

Run:

```bash
cd backend && uv run ruff check
cd backend && uv run pyright app/ tests/
cd backend && uv run pytest tests/ -v
```

Expected:

- Ruff: `All checks passed!`
- Pyright: `0 errors`
- Pytest: full suite PASS

- [ ] **Step 7: Commit the completed assistant rewrite**

```bash
git add backend/app/domains/assistant backend/app/bootstrap/container.py backend/app/bootstrap/routing.py backend/app/infra/database.py backend/tests/test_phase2_routes.py backend/tests/test_architecture_assistant_boundaries.py backend/tests/test_database.py backend/tests/test_assistant_threads_application.py backend/tests/test_assistant_router_application.py backend/tests/test_assistant_entity_resolution.py backend/tests/test_assistant_retrieval.py backend/tests/test_assistant_chat_application.py backend/tests/test_assistant_runtime.py docs/ARCHITECTURE.md
git rm backend/app/routers/assistant.py backend/app/services/assistant.py backend/app/services/assistant_context.py backend/app/services/assistant_runtime.py backend/tests/test_assistant_service.py backend/tests/test_assistant_context.py
git commit -m "refactor: replace assistant internals with retrieval-first domain slice"
```

## Self-Review Notes

Spec coverage check:

- backend-owned continuity: covered in Task 1 and Task 6
- deterministic routing and entity resolution: covered in Task 4
- targeted retrieval and evidence bundles: covered in Task 5
- global memory and evidence persistence: covered in Task 2 and Task 5
- API-stable internal rewrite with old internals deleted: covered in Task 7
- planner-ready substrate without implementing planner now: reflected in the file map and domain boundaries, while keeping this slice scoped to retrieval-first execution

Placeholder scan:

- No `TODO`, `TBD`, or “similar to X” placeholders remain.
- Every code-touching step includes concrete code or function signatures.
- Every test step includes an exact command and expected outcome.

Type consistency:

- Internal assistant evidence and memory types are introduced in Task 2 before later tasks use them.
- Port names stay consistent: `AssistantConversationStore`, `AssistantReadModelStore`, `AssistantRuntime`.
- The stream orchestrator stays named `stream_reply(...)` inside the new domain layer and is used consistently in later tasks.
