---
name: testing
description: How to write tests for this project — what to test, what to skip, and the equivalence-class discipline that prevents redundant or missing cases. Read before writing any test.
user-invocable: false
---

## Decision framework: what earns a test

Before writing anything, answer these questions:

**1. What are the branches?**
List every `if`/`elif`/`else` and every early return. Each branch is one required test.

**2. Where are the boundaries?**
Every `>=`, `<=`, `>`, `<` comparison earns *two* tests: one at exactly the limit, one on each side.

**3. What are the failure modes?**
Error paths are at least as important as happy paths.

**4. Does complexity scale with test count?**
Simple functions with no branching may need zero tests. Complex logic needs many.

**5. Would deleting this test let a regression slip through?**
If another test already covers the same branch and boundary, delete one.

---

## What NOT to test

**LLM outputs** — test what happens *given* certain outputs, not that the LLM was called.

**Prompt content** — asserting a prompt string contains specific text is brittle.

**That a mock was called** — assert on *outcomes*: return values, side effects, errors.

---

## Equivalence classes, not examples

One test per branch + two tests per boundary. Delete any parametrize case that exercises the same branch as another.

---

## Test naming

Name tests after the **behaviour under test**, not the function:

```python
# BAD
def test_execute_python():

# GOOD
def test_syntax_error_populates_error_field():
def test_timeout_populates_error_field():
```

---

## Running tests

```bash
cd backend && uv run pytest tests/ -v
```

---

## Reference

- `backend/tests/test_stats.py` — aggregation tests (branches: safe helpers empty/nonempty, daily aggregation with/without data, period summary from raw readings, HR zone boundaries, flatten)
- `backend/tests/test_parser.py` — extractor edge cases (branches: zero-value handling for wellness and HRV)
- `backend/tests/test_main.py` — API handler tests (branches: 404 not found, filesystem-missing fallback, happy path)
- `backend/tests/test_database.py` — DB round-trips and schema (branches: init, count rows valid/invalid, fingerprint, store/load, stale deletion)
- `backend/tests/test_watcher.py` — zip extraction safety (branches: valid archive, path traversal rejection)
