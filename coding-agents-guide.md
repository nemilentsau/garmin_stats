# Working with Coding Agents: Team Guidelines

**Last reviewed: February 2026**
**Review cadence: Monthly — this field moves fast and recommendations may shift with new model releases**

---

These guidelines reflect the current empirical evidence on what actually improves coding agent performance, drawn from recent benchmarking studies (Gloaguen et al., Feb 2026; Li et al. SkillsBench, Feb 2026; Lulla et al., Jan 2026; Chatlatanagulchai et al., Nov 2025) and operational experience from teams running agents at scale (OpenAI Codex team, Spotify, Anthropic). Where industry recommendations conflict with measured outcomes, we follow the data.

The core insight: **agents perform best in tightly constrained environments with minimal upfront instructions and strong mechanical feedback loops.** More context is not better context — but the right *procedural* context, in domains the model doesn't already know well, can be transformative. The key is knowing when you're in which regime.

---

## 1. Context Files (AGENTS.md / CLAUDE.md / .cursorrules)

### Keep them small and focused

Target 50–150 lines, under 500 words of instruction content. Every token loads on every request regardless of relevance. Frontier models reliably follow approximately 150–200 instructions total; the agent's own system prompt already consumes 50+. A bloated context file leaves almost no instruction budget for the actual task.

SkillsBench (Li et al., Feb 2026) provides the clearest quantitative evidence for sizing: 2–3 focused context modules are optimal (+18.6pp improvement), while 4+ modules show sharply diminishing returns (+5.9pp). Comprehensive documentation actually *hurts* performance (–2.9pp). The sweet spot is focused procedural guidance, not exhaustive reference material.

Auto-generated context files (via `/init` or equivalent) consistently degrade task success rates. Do not use them without heavy manual editing. SkillsBench tested self-generated Skills — where agents create their own procedural context before solving tasks — and found they provide zero or negative benefit (–1.3pp average across 5 model configurations). The failure modes are instructive: models either generate vague guidance ("use pandas for data processing" without specific API patterns) or fail to recognize they need specialized knowledge at all. Models cannot reliably author the procedural knowledge they benefit from consuming. Human curation is not optional.

### What belongs in the file

- **Build, test, and lint commands.** This is the single highest-value content. These are genuinely non-discoverable from code alone and are the one category where context files consistently help.
- **Pointers to deeper documentation.** Treat the file as a table of contents, not an encyclopedia. Example: `Architecture: see docs/ARCHITECTURE.md`
- **Genuinely non-obvious constraints** that cannot be enforced mechanically. Example: "This repo talks to a rate-limited external API; never make more than 2 concurrent requests in tests."
- **Dependency management tool** if it's not the obvious default for the language.

### What does not belong in the file

- **Codebase overviews and directory listings.** Agents can run `find` and `ls`. Empirical data shows overviews do not help agents locate relevant files any faster.
- **Style guides.** Use a linter instead. A linter fires only when relevant; a prose instruction burns context on every request.
- **Architecture descriptions.** Put these in a linked file that the agent reads on demand.
- **Anything a competent developer could discover by reading the code.** If `settings.py` is called `settings.py`, you don't need to say where settings are.
- **Anything that duplicates existing README, CONTRIBUTING.md, or docstrings.**

### The decision heuristic

For every line in your context file, ask: *"Could this be enforced by a linter, type checker, test, or CI gate instead?"* If yes, encode it there, not in prose. Mechanical enforcement is strictly superior — it fires only when relevant, it's verifiable, and it injects context at exactly the moment the agent needs it.

---

## 2. Domain Awareness: When Context Helps vs. Hurts

Not all codebases benefit equally from context files. The single most important factor determining whether additional context helps or hurts is how well the model's training data covers your domain.

### The domain spectrum

SkillsBench tested Skills efficacy across 11 domains and found a 10x range in benefit:

**High benefit (specialized domains, underrepresented in training data):** Healthcare (+51.9pp), Manufacturing (+41.9pp), Cybersecurity (+23.2pp), Natural Science (+21.9pp). These domains involve procedural knowledge — regulatory formats, scientific methodologies, domain-specific API patterns — that models rarely encounter in pretraining. Curated procedural context here is transformative.

**Moderate benefit:** Energy (+17.9pp), Office/White Collar (+17.8pp), Finance (+15.1pp), Media (+13.9pp). These domains have some training coverage but include specialized workflows (SEC filing analysis, Excel pivot table APIs, signal processing pipelines) where targeted procedural guidance helps.

**Low benefit (well-represented in training data):** Software Engineering (+4.5pp), Mathematics (+6.0pp). For standard Python/JS/TypeScript codebases — which is what most AGENTS.md files target — context files add minimal value and often hurt. Models already know how to write code; telling them how to write code wastes context.

### Practical implications

Assess your project honestly. If you're building a standard web application in Python or TypeScript, your AGENTS.md should be extremely minimal — build commands, a few pointers, and nothing else. The Gloaguen et al. data shows context files are net negative for well-documented software engineering repositories.

If your project involves specialized domain knowledge — insurance audit workflows, financial regulatory formats, scientific data processing, manufacturing optimization — invest in curated procedural Skills files. These are where the largest gains exist. Write step-by-step workflows with specific API calls, exact function signatures, and working code examples. Not "use pandas for data processing" but "use `openpyxl.worksheet.table` with `TableStyleMedium9` for pivot tables; here's a complete working example."

### Skills files vs. context files

A context file (AGENTS.md) loads on every request. A Skills file lives in a `skills/` directory and is read on demand when the agent determines it's relevant. For domain-specific procedural knowledge, Skills files are the better vehicle — they don't tax the context window on unrelated tasks, and they can include executable scripts and code templates alongside the instructions.

Structure domain knowledge as separate, focused Skills modules rather than cramming everything into the root context file. Each Skill should target one procedure or workflow. The evidence is clear: 2–3 focused modules outperform one comprehensive document.

---

## 3. Mechanical Enforcement over Prose Instructions

This is the single most impactful investment a team can make. Agents follow instructions, but instructions that are irrelevant to the current task add cognitive load without improving outcomes. Mechanical enforcement has zero cost when irrelevant and maximum impact when triggered.

### Linters with remediation messages

Write custom lint rules whose error messages contain the fix instruction. When the agent violates an architectural constraint, the linter error becomes the instruction — injected precisely when needed, not loaded preemptively on every task.

Example: Instead of writing "Warning codes must be string constants in settings.py" in your context file, write a CI check that greps for warning code definitions outside `settings.py` and fails with a message explaining where they belong.

### Type checking

Strict type checking (mypy strict, TypeScript strict, Rust's type system) replaces enormous amounts of prose instruction. "Use Pydantic v2 models, not dicts" is better expressed as a type signature that rejects dicts at compile time.

### Structural tests

Tests that assert architectural invariants — dependency directions, module boundaries, naming conventions — are more reliable than documentation. They can't go stale because they break the build when violated.

### CI as the feedback loop

The agent's development loop is: attempt → get feedback → correct. The richer and faster the feedback, the better the output. Invest in CI that runs quickly and produces clear, actionable error messages. A 30-second lint cycle that catches 80% of issues is worth more than a 10-minute full test suite that the agent has to wait for.

---

## 4. Progressive Disclosure of Context

Do not front-load everything the agent might need. Instead, organize knowledge so the agent starts with a small, stable entry point and reads deeper documentation on demand.

### Structure

```
AGENTS.md              ← ~100 lines, build commands + pointers
ARCHITECTURE.md        ← Top-level map of domains and layers
skills/                ← Focused procedural Skills (2-3 modules)
  ├── vendor-extraction/ ← Domain-specific workflow + code examples
  ├── data-pipeline/     ← Step-by-step procedures with API patterns
  └── testing-patterns/  ← Domain-specific test strategies
docs/
  ├── design/          ← Design decisions and rationale
  ├── specs/           ← Feature specifications
  └── references/      ← External library docs, API references
```

The agent reads `AGENTS.md` on every task. It reads `ARCHITECTURE.md` only when it needs to understand system structure. It reads specific Skills and docs only when working in that area. This is how you avoid the context window tax while still providing high-value procedural knowledge where it matters.

### Reference files for unfamiliar dependencies

For libraries or tools that are niche or poorly represented in training data, maintain a reference file (e.g., `docs/references/obscure-library-llms.txt`) containing API signatures, usage examples, and common pitfalls. Point to it from the context file. This is where context files add genuine value — bridging knowledge gaps the model can't fill from training data alone.

### When context actively hurts

SkillsBench found that 16 of 84 tasks showed *negative* Skills deltas — providing procedural context made performance worse. The pattern: tasks the model already handles well can be degraded by Skills that introduce conflicting guidance or unnecessary complexity. Before adding context for a workflow, verify the agent can't already do it well without help. If it can, the context is overhead with no upside.

---

## 5. Task Decomposition

Agents perform significantly better on well-scoped tasks than on vague, open-ended ones.

### Write prompts like issue tickets

Include: what the current behavior is, what the desired behavior is, which files are likely involved (if known), and acceptance criteria that can be verified mechanically (tests passing, linter clean, specific output).

### Scope to one concern

A prompt that says "fix the pagination bug and also refactor the auth middleware" will produce worse results on both tasks than two separate prompts. Agents handle depth better than breadth.

### Include verification instructions

Tell the agent how to confirm its work: which test command to run, which endpoint to hit, what output to expect. The best prompts create a closed feedback loop where the agent can self-validate.

---

## 6. Repository Design for Agent Legibility

The codebase itself is the most important form of context. A well-structured repository with clear boundaries and naming conventions outperforms any amount of prose instruction.

### Prefer boring, composable technology

Technologies with stable APIs, strong type systems, and heavy representation in training data are easier for agents to model. When choosing between a trendy library and a well-known one, prefer the well-known one unless there's a compelling technical reason.

### Make architecture mechanically enforced

Dependency direction rules, layer boundaries, and module interfaces should be validated by tests or linters, not described in documentation. If cross-module imports are forbidden, write a test that fails when they appear.

### Keep files reasonably sized

Very large files degrade agent performance. If a file exceeds 500 lines, consider whether it has a natural decomposition point. This isn't just good practice for humans — agents reason better over focused, single-responsibility files.

### Colocate tests with code

Agents are more likely to discover and run relevant tests when they're near the code being modified. Prefer `module/test_module.py` or `module/__tests__/` over a distant top-level `tests/` directory that mirrors the source tree.

---

## 7. Review and Quality

### Don't skip review; change what you review for

Human review of agent-generated code should focus on: correctness of the approach (did it solve the right problem?), architectural fitness (does this belong here?), and edge cases the agent may have missed. Reviewing for style, formatting, or naming is wasted human attention — that's what linters are for.

### Use agents to review agents

For routine checks — test coverage, documentation completeness, consistency with patterns — agent-to-agent review is effective and cheap. Reserve human review for judgment calls: security implications, user-facing behavior, and architectural decisions.

### Treat failures as system signals

When an agent produces bad output, the fix is almost never "try harder" or "add more instructions." Ask: what capability is missing? What feedback loop is broken? Encode the answer into tooling, not documentation.

---

## 8. Managing Technical Debt

Agent-generated code accumulates patterns — including suboptimal ones — through replication. Without active maintenance, drift is inevitable.

### Continuous cleanup over periodic refactors

Schedule recurring background tasks (daily or weekly) that scan for pattern violations, stale documentation, and architectural drift. Small, continuous corrections are cheaper than periodic large refactors.

### Documentation freshness

Context files and architecture docs that aren't maintained become actively harmful — the agent follows outdated instructions. Either enforce freshness mechanically (CI checks for staleness, automated doc-gardening) or keep documentation minimal enough that staleness is unlikely.

---

## 9. Model Selection and Cost Tradeoffs

The right model isn't always the most capable one. SkillsBench demonstrated that smaller models with curated Skills can outperform larger models without them: Claude Haiku 4.5 with Skills (27.7%) exceeded Claude Opus 4.5 without Skills (22.0%).

### Skills as a model cost lever

If your project involves domain-specific workflows, investing engineering time in curated Skills files and running a cheaper model may yield better results at lower cost than running the most expensive model with no procedural context. Gemini 3 Flash with Skills achieved the highest pass rate in SkillsBench (48.7%) while being 44% cheaper per task than Gemini 3 Pro, despite consuming 2.3x more input tokens — the lower per-token cost more than compensated.

This doesn't generalize to all tasks. For open-ended reasoning, architectural decisions, and novel problem-solving, model capability still dominates. But for procedural, domain-specific tasks with clear workflows — which is a large share of production engineering work — Skills investment can substitute for model spend.

### Harness matters too

SkillsBench found that how the agent harness implements Skills significantly affects outcomes. Claude Code showed the highest Skills utilization rate and largest improvements (+13.9pp to +23.3pp), reflecting its native Skills integration. Codex CLI frequently acknowledged Skills content but then ignored it, proceeding with its own approach. When choosing tools, consider how well the harness actually incorporates context, not just the underlying model capability.

---

## 10. What We Don't Know Yet

These are open questions where current evidence is insufficient. Revisit as the field evolves.

- **Domain-specific calibration.** SkillsBench showed a 10x range in Skills benefit across domains, but the sample sizes per domain are small (2–16 tasks). We don't yet have reliable guidance for calibrating context investment to a *specific* project's domain mix. A project that's 80% standard web development and 20% specialized financial logic needs a different strategy than one that's 100% either.
- **Long-horizon coherence.** We don't have good data on whether agent-generated codebases maintain architectural coherence over years. The OpenAI Codex team has 5 months of experience; that's not enough to draw conclusions.
- **Optimal context file structure.** The evidence says "less is more" and 2–3 focused modules beat comprehensive docs, but the optimal format — structured YAML vs. prose markdown, hierarchical vs. flat, instruction-only vs. instruction-plus-code-examples — hasn't been systematically tested. SkillsBench found that "detailed" and "compact" Skills both outperformed "comprehensive" ones, but the taxonomy is coarse.
- **Dynamic vs. static context.** The theoretical case for dynamic context retrieval (agents grep for what they need) over static context files is strong, but rigorous benchmarking is still nascent. The OpenAI Codex team's operational experience supports dynamic approaches; formal evaluation lags behind.
- **Multi-agent coordination.** Most evidence is for single-agent workflows. How context files affect agent-to-agent handoffs and multi-agent systems is largely unexplored. The OpenAI team's agent-to-agent review pattern is promising but unevaluated in benchmarks.
- **Skills quality in the wild.** SkillsBench used top-quartile quality Skills (scoring 9+/12). The ecosystem average is 6.2/12. Real-world performance with typical-quality Skills will be lower than benchmark results suggest. The gap between curated benchmark Skills and what teams actually write is an important unknown.
- **Skill-task matching.** SkillsBench paired each task with curated, relevant Skills. In practice, agents must discover which Skills are relevant from a larger collection. How discovery accuracy affects outcomes is untested.
