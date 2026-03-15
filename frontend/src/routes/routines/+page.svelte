<script lang="ts">
	import { onMount } from 'svelte';

	import {
		api,
		type AssistantArtifact,
		type AssistantArtifactInput,
		type CardTemplate,
		type RoutineAssignment,
		type RoutineSchedule
	} from '$lib/api';
	import { COLORS, withAlpha } from '$lib/colors';
	import { errorMessage, makeId } from '$lib/utils';

	type ArtifactKind = 'card_template' | 'routine_spec' | 'capability_request';

	const artifactStatusAccent: Record<string, string> = {
		validated: COLORS.respiration,
		invalid: COLORS.heartRate,
		activated: COLORS.bodyBattery,
		draft: COLORS.stress
	};

	const kindStarters: Record<ArtifactKind, Record<string, unknown>> = {
		card_template: {
			id: 'mindfulness-open-monitoring',
			name: 'Open Monitoring',
			renderer: 'timer_session',
			slot_default: 'evening',
			summary: 'Observe sensations without steering attention.',
			tags: ['mindfulness', 'hrv'],
			payload: {
				duration_minutes: 15,
				pattern: 'unguided',
				instructions: 'Let attention widen. Note body and breath without correcting them.',
				rating_prompts: [
					{ key: 'attention_stability', label: 'Attention stability', scale_min: 1, scale_max: 5 },
					{ key: 'mental_clarity', label: 'Mental clarity', scale_min: 1, scale_max: 5 }
				]
			}
		},
		routine_spec: {
			id: 'mindfulness-weekly-cycle',
			name: 'Mindfulness Weekly Cycle',
			cadence: 'weekly',
			start_date: '2026-03-16',
			status: 'active',
			tags: ['mindfulness', 'experiment'],
			notes: 'Builds the evening meditation schedule for HRV tracking.',
			assignments: [
				{
					id: 'mindfulness-open-monitoring-mon',
					card_template_id: 'mindfulness-open-monitoring',
					cycle_week: 1,
					weekday: 'monday',
					slot: 'evening',
					position: 10,
					prescription_override_json: {}
				}
			]
		},
		capability_request: {
			requested_renderer: 'guided_journal',
			reason: 'Need a journaling card with structured text prompts and reflection capture.',
			source_artifact_id: null,
			payload_example_json: {}
		}
	};

	let loading = $state(true);
	let saving = $state(false);
	let error: string | null = $state(null);

	let artifacts = $state<AssistantArtifact[]>([]);
	let cards = $state<CardTemplate[]>([]);
	let routines = $state<RoutineSchedule[]>([]);
	let assignmentsByRoutine = $state<Record<string, RoutineAssignment[]>>({});

	let artifactKind = $state<ArtifactKind>('card_template');
	let artifactJson = $state(JSON.stringify(kindStarters.card_template, null, 2));
	let sourceThreadId = $state('');
	let sourceSnapshotId = $state('');
	let showPayloads = $state<Record<string, boolean>>({});

	const cardsById = $derived.by(() =>
		Object.fromEntries(cards.map((card) => [card.id, card])) as Record<string, CardTemplate>
	);
	const inboxArtifacts = $derived.by(() =>
		artifacts.filter((artifact) => artifact.status !== 'activated')
	);
	const validatedCount = $derived.by(() =>
		artifacts.filter((artifact) => artifact.status === 'validated').length
	);
	const invalidCount = $derived.by(() =>
		artifacts.filter((artifact) => artifact.status === 'invalid').length
	);

	function artifactTargetId(artifact: AssistantArtifact): string | null {
		const payload = artifact.payload_json as Record<string, unknown>;
		return typeof payload.id === 'string' ? payload.id : null;
	}

	function artifactDelta(artifact: AssistantArtifact): string {
		if (artifact.kind === 'card_template') {
			const targetId = artifactTargetId(artifact);
			const existing = targetId ? cards.find((card) => card.id === targetId) : null;
			return existing ? 'Updates an active live card' : 'Creates a new live card';
		}
		if (artifact.kind === 'routine_spec') {
			const payload = artifact.payload_json as Record<string, unknown>;
			const targetId = artifactTargetId(artifact);
			const existing = targetId ? routines.find((routine) => routine.id === targetId) : null;
			const assignmentCount = Array.isArray(payload.assignments) ? payload.assignments.length : 0;
			return `${existing ? 'Updates' : 'Creates'} a live routine · ${assignmentCount} assignments`;
		}
		return 'Requests a renderer capability that the app does not ship yet';
	}

	function artifactSummary(artifact: AssistantArtifact): string {
		const payload = artifact.payload_json as Record<string, unknown>;
		if (artifact.kind === 'card_template') {
			return `${String(payload.renderer ?? 'unknown')} · ${String(payload.slot_default ?? 'unslotted')}`;
		}
		if (artifact.kind === 'routine_spec') {
			return `${String(payload.cadence ?? 'unknown')} cadence · starts ${String(payload.start_date ?? 'unknown')}`;
		}
		return String(payload.requested_renderer ?? 'missing capability');
	}

	function formatDate(date: string | null): string {
		if (!date) return 'Open-ended';
		return new Date(date).toLocaleDateString('en-US', {
			month: 'short',
			day: 'numeric',
			year: 'numeric'
		});
	}

	function assignmentLabel(assignment: RoutineAssignment): string {
		const card = cardsById[assignment.card_template_id];
		return card ? card.name : assignment.card_template_id;
	}

	async function loadPage() {
		error = null;
		const [artifactsResponse, cardsResponse, routinesResponse] = await Promise.all([
			api.getAssistantArtifacts(),
			api.getCards('active'),
			api.getRoutines('active')
		]);
		artifacts = artifactsResponse.artifacts;
		cards = cardsResponse.cards;
		routines = routinesResponse.routines;

		const assignmentResponses = await Promise.all(
			routinesResponse.routines.map(async (routine) => ({
				routineId: routine.id,
				assignments: (await api.getRoutineAssignments(routine.id)).assignments
			}))
		);
		assignmentsByRoutine = Object.fromEntries(
			assignmentResponses.map((entry) => [entry.routineId, entry.assignments])
		);
	}

	onMount(() => {
		void loadPage()
			.catch((e: unknown) => {
				error = errorMessage(e);
			})
			.finally(() => {
				loading = false;
			});
	});

	function loadStarter(kind: ArtifactKind) {
		artifactKind = kind;
		artifactJson = JSON.stringify(kindStarters[kind], null, 2);
	}

	async function submitArtifact() {
		saving = true;
		error = null;
		try {
			const payload = JSON.parse(artifactJson) as Record<string, unknown>;
			const request: AssistantArtifactInput = {
				id: makeId('artifact'),
				kind: artifactKind,
				schema_version: 1,
				source_thread_id: sourceThreadId || null,
				source_snapshot_id: sourceSnapshotId || null,
				payload_json: payload
			};
			await api.createAssistantArtifact(request);
			await loadPage();
		} catch (e: unknown) {
			error = errorMessage(e);
		} finally {
			saving = false;
		}
	}

	async function activateArtifact(artifactId: string) {
		saving = true;
		error = null;
		try {
			await api.activateAssistantArtifact(artifactId);
			await loadPage();
		} catch (e: unknown) {
			error = errorMessage(e);
		} finally {
			saving = false;
		}
	}

	function togglePayload(artifactId: string) {
		showPayloads = { ...showPayloads, [artifactId]: !showPayloads[artifactId] };
	}
</script>

<svelte:head>
	<title>Routines - Garmin Stats</title>
</svelte:head>

{#if loading}
	<section class="loading-shell">
		<div class="loading-card">Opening routine spec studio...</div>
	</section>
{:else}
	<section class="routines-shell">
		<div
			class="hero"
			style={`--hero-a: ${withAlpha(COLORS.respiration, '2f')}; --hero-b: ${withAlpha(COLORS.hrv, '2f')};`}
		>
			<div class="hero-copy">
				<p class="eyebrow">Spec Runtime</p>
				<h1>The assistant writes drafts. The app validates, previews, and compiles them.</h1>
				<p>
					No new schema, route, or UI branch is required for an ordinary new card. The only time code
					should appear is when a draft asks for a renderer family the app does not already understand.
				</p>
			</div>
			<div class="summary-row">
				<div class="summary-stat">
					<span>Inbox</span>
					<strong>{inboxArtifacts.length}</strong>
				</div>
				<div class="summary-stat">
					<span>Validated</span>
					<strong>{validatedCount}</strong>
				</div>
				<div class="summary-stat">
					<span>Invalid</span>
					<strong>{invalidCount}</strong>
				</div>
				<div class="summary-stat accent">
					<span>Live runtime</span>
					<strong>{routines.length + cards.length}</strong>
				</div>
			</div>
		</div>

		{#if error}
			<div class="error-banner">{error}</div>
		{/if}

		<div class="studio-grid">
			<section class="panel studio-panel">
				<div class="panel-head">
					<p>Draft Studio</p>
					<h2>Validate a structured artifact before it touches the live runtime.</h2>
				</div>

				<div class="kind-row">
					{#each ['card_template', 'routine_spec', 'capability_request'] as kind}
						<button
							class="kind-pill"
							class:active={artifactKind === kind}
							onclick={() => loadStarter(kind as ArtifactKind)}
						>
							{kind}
						</button>
					{/each}
				</div>

				<div class="input-grid">
					<label>
						<span>Source thread</span>
						<input bind:value={sourceThreadId} placeholder="assistant thread id (optional)" />
					</label>
					<label>
						<span>Source snapshot</span>
						<input bind:value={sourceSnapshotId} placeholder="context snapshot id (optional)" />
					</label>
				</div>

				<label class="wide-field">
					<span>Payload JSON</span>
					<textarea bind:value={artifactJson} rows="22"></textarea>
				</label>

				<div class="form-actions">
					<button class="ghost-btn" onclick={() => loadStarter(artifactKind)}>Reset starter</button>
					<button class="primary-action" onclick={submitArtifact} disabled={saving}>
						Create draft
					</button>
				</div>
			</section>

			<section class="panel inbox-panel">
				<div class="panel-head">
					<p>Draft Inbox</p>
					<h2>Activation is explicit. Drafts do nothing until you accept them.</h2>
				</div>

				{#if inboxArtifacts.length === 0}
					<div class="empty-card">No draft artifacts are waiting. Create one or ask the assistant to emit a structured spec.</div>
				{:else}
					<div class="artifact-list">
						{#each inboxArtifacts as artifact}
							<article class="artifact-card">
								<div class="artifact-topline">
									<div>
										<p>{artifact.kind}</p>
										<h3>{artifactTargetId(artifact) ?? artifact.id}</h3>
									</div>
									<span
										class="status-badge"
										style={`--status-accent: ${artifactStatusAccent[artifact.status] ?? '#8fa3b0'};`}
									>
										{artifact.status}
									</span>
								</div>

								<div class="artifact-meta">
									<span>{artifactSummary(artifact)}</span>
									<span>{artifactDelta(artifact)}</span>
								</div>

								{#if artifact.validation_errors.length > 0}
									<div class="error-list">
										{#each artifact.validation_errors as validationError}
											<p>{validationError}</p>
										{/each}
									</div>
								{/if}

								<div class="artifact-actions">
									<button class="ghost-btn" onclick={() => togglePayload(artifact.id)}>
										{showPayloads[artifact.id] ? 'Hide payload' : 'Show payload'}
									</button>
									{#if artifact.status === 'validated' && artifact.kind !== 'capability_request'}
										<button class="primary-action" onclick={() => activateArtifact(artifact.id)} disabled={saving}>
											Activate
										</button>
									{/if}
								</div>

								{#if showPayloads[artifact.id]}
									<pre class="payload-view">{JSON.stringify(artifact.payload_json, null, 2)}</pre>
								{/if}
							</article>
						{/each}
					</div>
				{/if}
			</section>
		</div>

		<div class="runtime-grid">
			<section class="panel">
				<div class="panel-head">
					<p>Live Routines</p>
					<h2>Compiled schedules running right now.</h2>
				</div>

				{#if routines.length === 0}
					<div class="empty-card">No live routines exist yet. Activate a validated routine spec draft.</div>
				{:else}
					<div class="runtime-list">
						{#each routines as routine}
							<div class="runtime-card">
								<div class="runtime-head">
									<div>
										<h3>{routine.name}</h3>
										<p>{routine.cadence} · starts {formatDate(routine.start_date)} · {routine.end_date ? `ends ${formatDate(routine.end_date)}` : 'no end date'}</p>
									</div>
									<span>{assignmentsByRoutine[routine.id]?.length ?? 0} assignments</span>
								</div>

								{#if routine.notes}
									<p class="runtime-note">{routine.notes}</p>
								{/if}

								<div class="assignment-list">
									{#each assignmentsByRoutine[routine.id] ?? [] as assignment}
										<div class="assignment-pill">
											<strong>{assignment.weekday.slice(0, 3)} · week {assignment.cycle_week}</strong>
											<span>{assignment.slot}</span>
											<small>{assignmentLabel(assignment)}</small>
										</div>
									{/each}
								</div>
							</div>
						{/each}
					</div>
				{/if}
			</section>

			<section class="panel">
				<div class="panel-head">
					<p>Card Library</p>
					<h2>Renderer-stable cards the assistant can schedule without more code.</h2>
				</div>

				{#if cards.length === 0}
					<div class="empty-card">No live cards exist yet. Activate a card template draft first.</div>
				{:else}
					<div class="runtime-list">
						{#each cards as card}
							<div class="runtime-card compact">
								<div class="runtime-head">
									<div>
										<h3>{card.name}</h3>
										<p>{card.renderer} · default {card.slot_default}</p>
									</div>
									<span>{card.tags.length} tags</span>
								</div>
								{#if card.summary}
									<p class="runtime-note">{card.summary}</p>
								{/if}
								<div class="tag-row">
									{#each card.tags as tag}
										<span>{tag}</span>
									{/each}
								</div>
							</div>
						{/each}
					</div>
				{/if}
			</section>
		</div>
	</section>
{/if}

<style>
	.routines-shell {
		display: flex;
		flex-direction: column;
		gap: 18px;
	}

	.loading-shell {
		padding: 32px 0;
	}

	.loading-card,
	.error-banner,
	.empty-card {
		font-family: 'DM Mono', monospace;
		font-size: 12px;
		color: #95aab7;
		padding: 14px 16px;
		border-radius: 18px;
		border: 1px solid rgba(255, 255, 255, 0.08);
		background: rgba(255, 255, 255, 0.03);
	}

	.hero {
		display: grid;
		grid-template-columns: minmax(0, 1.4fr) minmax(320px, 0.9fr);
		gap: 18px;
		padding: 24px;
		border-radius: 28px;
		border: 1px solid rgba(255, 255, 255, 0.08);
		background:
			radial-gradient(circle at top left, var(--hero-a), transparent 38%),
			radial-gradient(circle at bottom right, var(--hero-b), transparent 42%),
			linear-gradient(145deg, rgba(10, 20, 32, 0.9), rgba(15, 27, 41, 0.84));
	}

	.eyebrow,
	.panel-head p,
	label span,
	.runtime-head span,
	.runtime-head p,
	.artifact-card p:first-child,
	.assignment-pill span,
	.assignment-pill small {
		margin: 0;
		font-family: 'DM Mono', monospace;
		font-size: 11px;
		text-transform: uppercase;
		letter-spacing: 0.14em;
		color: #8fa3b0;
	}

	.hero-copy h1,
	.panel-head h2 {
		margin: 8px 0 0;
		font-size: clamp(28px, 4vw, 40px);
		line-height: 1.04;
		color: #eef5f8;
		max-width: 14ch;
	}

	.hero-copy p:last-child {
		max-width: 58ch;
		color: #abc0cb;
		line-height: 1.6;
	}

	.summary-row,
	.studio-grid,
	.runtime-grid,
	.input-grid {
		display: grid;
		gap: 12px;
	}

	.summary-row {
		grid-template-columns: repeat(2, minmax(0, 1fr));
		align-content: start;
	}

	.summary-stat,
	.panel,
	.runtime-card,
	.artifact-card {
		padding: 16px;
		border-radius: 22px;
		background: rgba(255, 255, 255, 0.035);
		border: 1px solid rgba(255, 255, 255, 0.08);
	}

	.summary-stat span {
		display: block;
		font-family: 'DM Mono', monospace;
		font-size: 11px;
		text-transform: uppercase;
		letter-spacing: 0.14em;
		color: #8fa3b0;
	}

	.summary-stat strong {
		display: block;
		margin-top: 10px;
		font-size: 30px;
	}

	.summary-stat.accent {
		background: linear-gradient(140deg, rgba(91, 181, 166, 0.12), rgba(155, 107, 205, 0.12));
	}

	.studio-grid,
	.runtime-grid {
		grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
	}

	.panel {
		display: flex;
		flex-direction: column;
		gap: 14px;
	}

	.panel-head h2 {
		font-size: 24px;
		max-width: none;
	}

	.kind-row {
		display: flex;
		flex-wrap: wrap;
		gap: 8px;
	}

	.kind-pill,
	.ghost-btn,
	.primary-action {
		border: 0;
		cursor: pointer;
		font: inherit;
	}

	.kind-pill,
	.ghost-btn {
		padding: 11px 13px;
		border-radius: 999px;
		background: rgba(255, 255, 255, 0.05);
		color: #d3dfe7;
	}

	.kind-pill.active {
		background: rgba(91, 181, 166, 0.16);
		color: #7be0d0;
	}

	.primary-action {
		padding: 11px 14px;
		border-radius: 999px;
		background: linear-gradient(135deg, rgba(91, 181, 166, 0.92), rgba(74, 144, 217, 0.88));
		color: #08111d;
		font-weight: 700;
	}

	.input-grid {
		grid-template-columns: repeat(2, minmax(0, 1fr));
	}

	label,
	.wide-field {
		display: flex;
		flex-direction: column;
		gap: 8px;
	}

	input,
	textarea {
		border: 1px solid rgba(255, 255, 255, 0.1);
		background: rgba(8, 15, 24, 0.88);
		color: #eef5f8;
		border-radius: 14px;
		padding: 11px 12px;
		font: inherit;
	}

	textarea {
		resize: vertical;
		font-family: 'DM Mono', monospace;
		font-size: 12px;
		line-height: 1.5;
	}

	.form-actions,
	.artifact-actions,
	.runtime-head,
	.assignment-list,
	.tag-row,
	.artifact-meta {
		display: flex;
		flex-wrap: wrap;
		gap: 10px;
	}

	.form-actions,
	.artifact-actions,
	.runtime-head {
		justify-content: space-between;
		align-items: center;
	}

	.artifact-list,
	.runtime-list {
		display: flex;
		flex-direction: column;
		gap: 12px;
	}

	.artifact-topline,
	.runtime-head {
		display: flex;
		align-items: flex-start;
		justify-content: space-between;
		gap: 12px;
	}

	.artifact-topline h3,
	.runtime-card h3 {
		margin: 8px 0 0;
		font-size: 22px;
	}

	.status-badge {
		padding: 8px 10px;
		border-radius: 999px;
		background: color-mix(in srgb, var(--status-accent) 16%, transparent);
		color: var(--status-accent);
		font-family: 'DM Mono', monospace;
		font-size: 11px;
		text-transform: uppercase;
		letter-spacing: 0.14em;
	}

	.artifact-meta span,
	.runtime-note,
	.assignment-pill strong,
	.tag-row span {
		color: #a8bac6;
	}

	.error-list {
		padding: 12px 14px;
		border-radius: 16px;
		background: rgba(232, 93, 74, 0.08);
		border: 1px solid rgba(232, 93, 74, 0.18);
	}

	.error-list p {
		margin: 0;
		color: #f2a399;
		line-height: 1.55;
	}

	.payload-view {
		margin: 0;
		padding: 14px;
		border-radius: 18px;
		background: rgba(8, 15, 24, 0.88);
		border: 1px solid rgba(255, 255, 255, 0.06);
		color: #d6e4ec;
		font-family: 'DM Mono', monospace;
		font-size: 12px;
		overflow-x: auto;
	}

	.assignment-pill,
	.tag-row span {
		padding: 10px 12px;
		border-radius: 16px;
		background: rgba(255, 255, 255, 0.04);
	}

	.assignment-pill strong,
	.tag-row span {
		display: block;
	}

	.runtime-note {
		margin: 0;
		line-height: 1.55;
	}

	.runtime-card.compact .runtime-note {
		margin-bottom: 0;
	}

	@media (max-width: 980px) {
		.hero,
		.studio-grid,
		.runtime-grid,
		.input-grid {
			grid-template-columns: 1fr;
		}
	}
</style>
