<script lang="ts">
	import { onMount } from 'svelte';
	import {
		api,
		type Experiment,
		type ExperimentInput,
		type Routine,
		type TargetMetricDefinition
	} from '$lib/api';
	import { COLORS } from '$lib/colors';

	const statusAccent: Record<string, string> = {
		draft: COLORS.skinTemp,
		active: COLORS.hrv,
		paused: COLORS.bodyBattery,
		completed: COLORS.heartRateResting,
		abandoned: COLORS.heartRate
	};

	let loading = $state(true);
	let saving = $state(false);
	let error: string | null = $state(null);

	let experiments: Experiment[] = $state([]);
	let routines: Routine[] = $state([]);
	let metrics: TargetMetricDefinition[] = $state([]);
	let editingId = $state('');

	let form = $state<Required<Pick<ExperimentInput, 'id' | 'name' | 'status' | 'start_date' | 'end_date' | 'goal' | 'hypothesis' | 'linked_routine_ids' | 'outcome_metrics' | 'expected_lag_days' | 'confounder_notes' | 'priority'>>>({
		id: '',
		name: '',
		status: 'draft',
		start_date: '',
		end_date: '',
		goal: '',
		hypothesis: '',
		linked_routine_ids: [],
		outcome_metrics: [],
		expected_lag_days: [1],
		confounder_notes: '',
		priority: 0
	});

	function makeId(prefix: string): string {
		return `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
	}

	async function loadPage() {
		error = null;
		const [experimentsResponse, routinesResponse, metricsResponse] = await Promise.all([
			api.getExperiments(),
			api.getRoutines(),
			api.getTargetMetrics()
		]);
		experiments = experimentsResponse.experiments;
		routines = routinesResponse.routines;
		metrics = metricsResponse.metrics;
	}

	onMount(() => {
		void loadPage()
			.catch((e: unknown) => {
				error = e instanceof Error ? e.message : String(e);
			})
			.finally(() => {
				loading = false;
			});
	});

	function toggleMetric(metricKey: string) {
		form.outcome_metrics = form.outcome_metrics.includes(metricKey)
			? form.outcome_metrics.filter((item) => item !== metricKey)
			: [...form.outcome_metrics, metricKey];
	}

	function toggleRoutine(routineId: string) {
		form.linked_routine_ids = form.linked_routine_ids.includes(routineId)
			? form.linked_routine_ids.filter((item) => item !== routineId)
			: [...form.linked_routine_ids, routineId];
	}

	function setLagPreset(days: number[]) {
		form.expected_lag_days = days;
	}

	function beginEdit(experiment: Experiment) {
		editingId = experiment.id;
		form.id = experiment.id;
		form.name = experiment.name;
		form.status = experiment.status;
		form.start_date = experiment.start_date ?? '';
		form.end_date = experiment.end_date ?? '';
		form.goal = experiment.goal ?? '';
		form.hypothesis = experiment.hypothesis ?? '';
		form.linked_routine_ids = [...experiment.linked_routine_ids];
		form.outcome_metrics = [...experiment.outcome_metrics];
		form.expected_lag_days = [...experiment.expected_lag_days];
		form.confounder_notes = experiment.confounder_notes ?? '';
		form.priority = experiment.priority;
	}

	function resetForm() {
		editingId = '';
		form.id = '';
		form.name = '';
		form.status = 'draft';
		form.start_date = '';
		form.end_date = '';
		form.goal = '';
		form.hypothesis = '';
		form.linked_routine_ids = [];
		form.outcome_metrics = [];
		form.expected_lag_days = [1];
		form.confounder_notes = '';
		form.priority = 0;
	}

	async function submitExperiment() {
		saving = true;
		error = null;
		try {
			const payload: ExperimentInput = {
				...form,
				id: editingId || makeId('exp'),
				start_date: form.start_date || null,
				end_date: form.end_date || null,
				goal: form.goal || null,
				hypothesis: form.hypothesis || null,
				confounder_notes: form.confounder_notes || null
			};

			if (editingId) {
				await api.updateExperiment(editingId, payload);
			} else {
				await api.createExperiment(payload);
			}

			const response = await api.getExperiments();
			experiments = response.experiments;
			resetForm();
		} catch (e: unknown) {
			error = e instanceof Error ? e.message : String(e);
		} finally {
			saving = false;
		}
	}

	let activeCount = $derived.by(() => experiments.filter((item) => item.status === 'active').length);
	let draftCount = $derived.by(() => experiments.filter((item) => item.status === 'draft').length);
	let linkedRoutineCount = $derived.by(
		() => new Set(experiments.flatMap((item) => item.linked_routine_ids)).size
	);
</script>

{#if loading}
	<section class="loading-shell">
		<div class="loading-card">Loading experiments foundation...</div>
	</section>
{:else}
	<section class="experiments-shell">
		<div class="hero-band">
			<div>
				<p class="eyebrow">Phase 1 foundation</p>
				<h1>Turn rough ideas into trackable experiments before the analysis engine arrives.</h1>
				<p class="hero-copy">
					Define what you are trying, why you think it might matter, which routines belong to the
					test, and which recovery metrics should watch it. Phase 1 stops here on purpose: setup now,
					evidence in Phase 3.
				</p>
			</div>
			<div class="hero-stats">
				<div class="hero-stat">
					<span>Active</span>
					<strong>{activeCount}</strong>
				</div>
				<div class="hero-stat">
					<span>Drafts</span>
					<strong>{draftCount}</strong>
				</div>
				<div class="hero-stat">
					<span>Linked routines</span>
					<strong>{linkedRoutineCount}</strong>
				</div>
			</div>
		</div>

		{#if error}
			<div class="error-banner">{error}</div>
		{/if}

		<div class="experiments-grid">
			<section class="panel form-panel">
				<div class="panel-head">
					<p>{editingId ? 'Edit experiment' : 'Create experiment'}</p>
					<h2>{editingId ? 'Refine the hypothesis' : 'Define the test clearly'}</h2>
				</div>
				<div class="field-grid">
					<label>
						<span>Name</span>
						<input bind:value={form.name} placeholder="Evening meditation block" />
					</label>
					<label>
						<span>Status</span>
						<select bind:value={form.status}>
							<option value="draft">draft</option>
							<option value="active">active</option>
							<option value="paused">paused</option>
							<option value="completed">completed</option>
							<option value="abandoned">abandoned</option>
						</select>
					</label>
					<label>
						<span>Start date</span>
						<input type="date" bind:value={form.start_date} />
					</label>
					<label>
						<span>End date</span>
						<input type="date" bind:value={form.end_date} />
					</label>
					<label class="wide">
						<span>Goal</span>
						<input bind:value={form.goal} placeholder="Raise nightly HRV and lower evening stress" />
					</label>
					<label class="wide">
						<span>Hypothesis</span>
						<textarea
							bind:value={form.hypothesis}
							rows="3"
							placeholder="I expect a 10-minute meditation before bed to improve next-morning HRV."
						></textarea>
					</label>
					<label class="wide">
						<span>Confounder notes</span>
						<textarea
							bind:value={form.confounder_notes}
							rows="3"
							placeholder="Travel week, marathon prep, alcohol, late meals..."
						></textarea>
					</label>
				</div>

				<div class="selection-block">
					<div class="selection-head">
						<span>Linked routines</span>
						<p>Choose the behaviors that belong to this test.</p>
					</div>
					<div class="chip-grid">
						{#each routines as routine}
							<button
								class:selected={form.linked_routine_ids.includes(routine.id)}
								class="chip"
								onclick={() => toggleRoutine(routine.id)}
							>
								{routine.name}
							</button>
						{/each}
					</div>
				</div>

				<div class="selection-block">
					<div class="selection-head">
						<span>Outcome metrics</span>
						<p>Pick only the signals that matter for this question.</p>
					</div>
					<div class="metric-grid">
						{#each metrics as metric}
							<button
								class:selected={form.outcome_metrics.includes(metric.key)}
								class="metric-chip"
								onclick={() => toggleMetric(metric.key)}
							>
								<strong>{metric.label}</strong>
								<small>{metric.unit} · {metric.path}</small>
							</button>
						{/each}
					</div>
				</div>

				<div class="selection-block">
					<div class="selection-head">
						<span>Lag preset</span>
						<p>Mark when you expect the effect to show up.</p>
					</div>
					<div class="chip-grid">
						<button class:selected={form.expected_lag_days.join(',') === '1'} class="chip" onclick={() => setLagPreset([1])}>next morning</button>
						<button class:selected={form.expected_lag_days.join(',') === '1,2,3'} class="chip" onclick={() => setLagPreset([1, 2, 3])}>1-3 days</button>
						<button class:selected={form.expected_lag_days.join(',') === '3,7'} class="chip" onclick={() => setLagPreset([3, 7])}>block effect</button>
					</div>
				</div>

				<div class="actions">
					<button class="primary-action" onclick={submitExperiment} disabled={saving || !form.name || form.outcome_metrics.length === 0}>
						{editingId ? 'Update experiment' : 'Create experiment'}
					</button>
					{#if editingId}
						<button class="ghost-action" onclick={resetForm}>Cancel edit</button>
					{/if}
				</div>
			</section>

			<section class="panel board-panel">
				<div class="panel-head">
					<p>Experiment board</p>
					<h2>{experiments.length === 0 ? 'No experiments yet' : `${experiments.length} active questions`}</h2>
				</div>
				<div class="board-list">
					{#if experiments.length === 0}
						<div class="empty-card">Create the first experiment to establish the questions your data should answer.</div>
					{:else}
						{#each experiments as experiment}
							<button class="experiment-card" onclick={() => beginEdit(experiment)}>
								<div class="card-head">
									<div>
										<p class="card-label">{experiment.name}</p>
										<h3>{experiment.goal || 'Goal still being defined'}</h3>
									</div>
									<span class="status-pill" style={`background:${statusAccent[experiment.status] ?? '#8a9baa'}20;color:${statusAccent[experiment.status] ?? '#8a9baa'}`}>
										{experiment.status}
									</span>
								</div>
								<p class="card-copy">{experiment.hypothesis || 'No hypothesis yet. Tighten this before starting analysis.'}</p>
								<div class="meta-strip">
									<div>
										<span>Metrics</span>
										<strong>{experiment.outcome_metrics.length}</strong>
									</div>
									<div>
										<span>Routines</span>
										<strong>{experiment.linked_routine_ids.length}</strong>
									</div>
									<div>
										<span>Lag</span>
										<strong>{experiment.expected_lag_days.join(', ') || 'n/a'}</strong>
									</div>
								</div>
							</button>
						{/each}
					{/if}
				</div>
			</section>
		</div>
	</section>
{/if}

<style>
	.experiments-shell {
		display: grid;
		gap: 22px;
	}

	.loading-shell {
		padding: 48px 0;
	}

	.loading-card,
	.error-banner,
	.panel {
		border: 1px solid rgba(255, 255, 255, 0.08);
		background:
			linear-gradient(135deg, rgba(14, 23, 36, 0.95), rgba(8, 14, 25, 0.92)),
			radial-gradient(circle at top left, rgba(155, 107, 205, 0.12), transparent 45%);
		border-radius: 22px;
		box-shadow: 0 24px 60px rgba(0, 0, 0, 0.24);
	}

	.hero-band {
		display: grid;
		grid-template-columns: minmax(0, 1.4fr) minmax(280px, 0.8fr);
		gap: 18px;
		padding: 28px;
		border-radius: 26px;
		border: 1px solid rgba(255, 255, 255, 0.08);
		background:
			radial-gradient(circle at top right, rgba(155, 107, 205, 0.18), transparent 35%),
			radial-gradient(circle at bottom left, rgba(201, 147, 58, 0.16), transparent 32%),
			linear-gradient(140deg, rgba(11, 19, 31, 0.96), rgba(15, 23, 35, 0.9));
	}

	.eyebrow,
	.panel-head p,
	.card-label {
		margin: 0 0 8px;
		font-family: 'DM Mono', monospace;
		font-size: 11px;
		letter-spacing: 0.18em;
		text-transform: uppercase;
		color: #c9a47d;
	}

	h1,
	h2,
	h3 {
		margin: 0;
		color: #f3f7fb;
	}

	h1 {
		font-size: clamp(2rem, 5vw, 3.2rem);
		line-height: 0.96;
		max-width: 13ch;
	}

	.hero-copy,
	.card-copy,
	.empty-card {
		margin: 16px 0 0;
		color: #9bb0bf;
		line-height: 1.6;
	}

	.hero-stats,
	.experiments-grid,
	.field-grid,
	.chip-grid,
	.metric-grid,
	.actions,
	.board-list,
	.meta-strip,
	.card-head {
		display: grid;
	}

	.hero-stats {
		grid-template-columns: 1fr;
		gap: 12px;
	}

	.hero-stat {
		padding: 16px 18px;
		border-radius: 18px;
		background: rgba(255, 255, 255, 0.04);
	}

	.hero-stat span,
	.meta-strip span,
	.selection-head span,
	label span {
		display: block;
		margin-bottom: 8px;
		font-family: 'DM Mono', monospace;
		font-size: 11px;
		letter-spacing: 0.08em;
		text-transform: uppercase;
		color: #8da0af;
	}

	.hero-stat strong,
	.meta-strip strong {
		font-size: 1.65rem;
		color: #f8fbff;
	}

	.error-banner,
	.panel {
		padding: 22px;
	}

	.experiments-grid {
		grid-template-columns: minmax(0, 1.05fr) minmax(320px, 0.95fr);
		gap: 18px;
	}

	.field-grid {
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: 14px;
	}

	.wide {
		grid-column: 1 / -1;
	}

	input,
	select,
	textarea,
	button {
		font: inherit;
	}

	input,
	select,
	textarea {
		width: 100%;
		border: 1px solid rgba(255, 255, 255, 0.08);
		background: rgba(255, 255, 255, 0.04);
		color: #f2f7fb;
		border-radius: 14px;
		padding: 12px 14px;
		box-sizing: border-box;
	}

	textarea {
		resize: vertical;
		min-height: 92px;
	}

	.selection-block {
		margin-top: 18px;
		padding-top: 18px;
		border-top: 1px solid rgba(255, 255, 255, 0.08);
	}

	.selection-head p {
		margin-top: 0;
		margin-bottom: 12px;
		color: #8da0af;
		font-size: 0.95rem;
	}

	.chip-grid,
	.metric-grid {
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: 10px;
	}

	.chip,
	.metric-chip,
	.experiment-card,
	.empty-card,
	.ghost-action {
		border: 1px solid rgba(255, 255, 255, 0.08);
		background: rgba(255, 255, 255, 0.035);
		border-radius: 18px;
	}

	.chip,
	.metric-chip,
	.experiment-card,
	.ghost-action {
		cursor: pointer;
	}

	.chip,
	.ghost-action {
		padding: 12px 14px;
		color: #e3edf5;
	}

	.metric-chip {
		display: grid;
		gap: 6px;
		padding: 14px;
		text-align: left;
		color: #edf5fb;
	}

	.metric-chip small {
		font-family: 'DM Mono', monospace;
		font-size: 11px;
		color: #91a5b5;
	}

	.chip.selected,
	.metric-chip.selected {
		border-color: rgba(155, 107, 205, 0.42);
		box-shadow: inset 0 0 0 1px rgba(155, 107, 205, 0.25);
		background: rgba(155, 107, 205, 0.12);
	}

	.actions {
		grid-template-columns: auto auto;
		gap: 12px;
		margin-top: 18px;
	}

	.primary-action,
	.ghost-action {
		padding: 12px 18px;
		border-radius: 999px;
		font-weight: 600;
	}

	.primary-action {
		border: 0;
		background: linear-gradient(90deg, #c9933a, #e7bf78);
		color: #121822;
	}

	.primary-action:disabled {
		opacity: 0.55;
		cursor: not-allowed;
	}

	.board-list {
		gap: 12px;
	}

	.experiment-card,
	.empty-card {
		padding: 16px;
		text-align: left;
	}

	.card-head,
	.meta-strip {
		grid-template-columns: minmax(0, 1fr) auto;
		gap: 12px;
		align-items: start;
	}

	.status-pill {
		padding: 6px 10px;
		border-radius: 999px;
		font-family: 'DM Mono', monospace;
		font-size: 11px;
		letter-spacing: 0.08em;
		text-transform: uppercase;
	}

	.meta-strip {
		grid-template-columns: repeat(3, minmax(0, 1fr));
		margin-top: 16px;
		padding-top: 14px;
		border-top: 1px solid rgba(255, 255, 255, 0.08);
	}

	@media (max-width: 980px) {
		.hero-band,
		.experiments-grid,
		.field-grid,
		.chip-grid,
		.metric-grid,
		.actions {
			grid-template-columns: 1fr;
		}

		h1 {
			max-width: none;
		}
	}
</style>
