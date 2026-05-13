<svelte:head>
	<title>Experiments - Garmin Stats</title>
</svelte:head>

<script lang="ts">
	import { onMount } from 'svelte';
	import {
		api,
		type ExperimentsResponse,
		type ExperimentWithAnalysis,
		type ExperimentAnalysis,
		type ExperimentInput,
		type ExperimentPreviewResponse
	} from '$lib/api';
	import { startRealtimePage } from '$lib/realtime-page';
	import { errorMessage } from '$lib/utils';
	import ConfidenceBadge from '$lib/components/experiments/ConfidenceBadge.svelte';
	import ExperimentTimeline from '$lib/components/experiments/ExperimentTimeline.svelte';
	import MetricComparison from '$lib/components/experiments/MetricComparison.svelte';
	import AdherenceCalendar from '$lib/components/experiments/AdherenceCalendar.svelte';
	import ConfounderPanel from '$lib/components/experiments/ConfounderPanel.svelte';

	let data: ExperimentsResponse | null = $state(null);
	let selectedId: string | null = $state(null);
	let detail: ExperimentWithAnalysis | null = $state(null);
	let loading = $state(true);
	let error: string | null = $state(null);

	const today = new Date().toISOString().slice(0, 10);

	async function fetchData() {
		data = await api.getExperiments();
		loading = false;
		if (selectedId) {
			detail = await api.getExperiment(selectedId);
		}
	}

	function setError(e: string) {
		error = e;
	}
	function setLoading(v: boolean) {
		loading = v;
	}

	onMount(() => startRealtimePage({ fetchData, setError, setLoading }));

	async function selectExperiment(id: string) {
		selectedId = id;
		detail = await api.getExperiment(id);
	}

	function backToList() {
		selectedId = null;
		detail = null;
	}

	function statusColor(status: string): string {
		if (status === 'active') return '#5BB5A6';
		if (status === 'completed') return '#4CAF82';
		return '#5e7282';
	}

	function headlineEffect(a: ExperimentAnalysis | null): string {
		if (!a || !a.metrics.length) return 'No data yet';
		const m = a.metrics[0];
		const r = m.best_result;
		const sign = r.delta_pct > 0 ? '+' : '';
		return `${m.path}: ${sign}${r.delta_pct.toFixed(1)}%`;
	}

	/* ── Import modal ── */
	type ImportStep = 'idle' | 'previewing' | 'preview-ok' | 'preview-error' | 'importing' | 'done';
	let importModalOpen = $state(false);
	let importStep = $state<ImportStep>('idle');
	let importSpec = $state<ExperimentInput | null>(null);
	let importPreview = $state<ExperimentPreviewResponse | null>(null);
	let importResult = $state<ExperimentWithAnalysis | null>(null);
	let importError = $state<string | null>(null);
	let fileInputEl: HTMLInputElement | undefined = $state();

	function openImportModal(): void {
		importModalOpen = true;
		importStep = 'idle';
		importSpec = null;
		importPreview = null;
		importResult = null;
		importError = null;
	}

	function closeImportModal(): void {
		importModalOpen = false;
	}

	async function handleFile(file: File): Promise<void> {
		importError = null;
		try {
			const text = await file.text();
			const spec = JSON.parse(text) as ExperimentInput;
			importSpec = spec;
			importStep = 'previewing';
			const preview = await api.previewExperiment(spec);
			importPreview = preview;
			importStep = preview.valid ? 'preview-ok' : 'preview-error';
		} catch (e: unknown) {
			importError = errorMessage(e);
			importStep = 'idle';
		}
	}

	function onFileInput(e: Event): void {
		const input = e.currentTarget as HTMLInputElement;
		const file = input.files?.[0];
		if (file) void handleFile(file);
		input.value = '';
	}

	function onDrop(e: DragEvent): void {
		e.preventDefault();
		const file = e.dataTransfer?.files[0];
		if (file && file.name.endsWith('.json')) void handleFile(file);
	}

	async function handleImport(): Promise<void> {
		if (!importSpec) return;
		importError = null;
		try {
			importStep = 'importing';
			const result = await api.importExperiment(importSpec);
			importResult = result;
			importStep = 'done';
			data = await api.getExperiments();
		} catch (e: unknown) {
			importError = errorMessage(e);
			importStep = 'preview-ok';
		}
	}

	function resetImport(): void {
		importStep = 'idle';
		importSpec = null;
		importPreview = null;
		importError = null;
	}
</script>

{#if error}
	<div class="mb-4 rounded-lg bg-[rgba(232,93,74,0.1)] px-4 py-3 text-sm text-[#E85D4A]">
		{error}
	</div>
{/if}

{#if loading}
	<div class="flex min-h-[40vh] items-center justify-center">
		<div class="text-[#5e7282]">Loading experiments...</div>
	</div>
{:else if selectedId && detail}
	<!-- Detail view -->
	{@const exp = detail.experiment}
	{@const analysis = detail.analysis}

	<div class="mx-auto max-w-4xl space-y-6 py-4">
		<div>
			<button
				class="mb-3 text-[13px] text-[#5e7282] hover:text-[#8a9baa] transition-colors"
				onclick={backToList}
			>
				&larr; All experiments
			</button>
			<div class="flex items-start justify-between">
				<div>
					<h1 class="text-2xl font-bold text-[#e8f0f5]">{exp.name}</h1>
					{#if exp.hypothesis}
						<p class="mt-1 text-sm text-[#8a9baa]">{exp.hypothesis}</p>
					{/if}
				</div>
				<div class="flex items-center gap-3">
					<span
						class="rounded-full px-3 py-1 text-[11px] font-medium uppercase tracking-wider"
						style="color: {statusColor(exp.status)}; background: {statusColor(exp.status)}22;"
					>
						{exp.status}
					</span>
					{#if analysis}
						<ConfidenceBadge confidence={analysis.overall_confidence} />
					{/if}
				</div>
			</div>
		</div>

		{#if analysis}
			<div class="rounded-xl border border-[rgba(255,255,255,0.05)] bg-[rgba(255,255,255,0.02)] px-5 py-4">
				<p class="text-sm text-[#b8c8d4]">{analysis.summary}</p>
			</div>

			{#if exp.design && exp.design.baseline_start_date && exp.design.baseline_end_date && exp.design.treatment_start_date}
				<ExperimentTimeline
					baselineStart={exp.design.baseline_start_date}
					baselineEnd={exp.design.baseline_end_date}
					treatmentStart={exp.design.treatment_start_date}
					treatmentEnd={exp.design.treatment_end_date}
					currentDate={today}
				/>
			{/if}

			<AdherenceCalendar
				entries={analysis.adherence_by_day}
				treatmentStart={exp.design?.treatment_start_date ?? analysis.adherence_by_day[0]?.date ?? today}
				treatmentEnd={exp.design?.treatment_end_date ?? null}
				currentDate={today}
			/>

			<div class="space-y-4">
				{#each analysis.metrics as metric}
					<MetricComparison {metric} />
				{/each}
			</div>

			<ConfounderPanel confounders={analysis.confounders} />
		{:else}
			<div class="flex min-h-[20vh] items-center justify-center text-[#5e7282]">
				No analysis available. Import an experiment with a design to see results.
			</div>
		{/if}
	</div>
{:else}
	<!-- List view -->
	<div class="mx-auto max-w-4xl py-4">
		<div class="mb-6 flex items-center justify-between">
			<h1 class="text-2xl font-bold text-[#e8f0f5]">Experiments</h1>
			<button type="button" class="import-btn" onclick={openImportModal}>Import</button>
		</div>

		{#if data && data.experiments.length > 0}
			<div class="space-y-3">
				{#each data.experiments as item}
					{@const exp = item.experiment}
					{@const analysis = item.analysis}
					<button
						class="w-full rounded-xl border border-[rgba(255,255,255,0.05)] bg-[rgba(255,255,255,0.02)] p-5 text-left transition-colors hover:border-[rgba(255,255,255,0.1)] hover:bg-[rgba(255,255,255,0.04)]"
						onclick={() => selectExperiment(exp.id)}
					>
						<div class="flex items-center justify-between">
							<div class="min-w-0 flex-1">
								<div class="flex items-center gap-3">
									<h2 class="text-lg font-semibold text-[#e8f0f5]">{exp.name}</h2>
									<span
										class="rounded-full px-2 py-0.5 text-[10px] font-medium uppercase tracking-wider"
										style="color: {statusColor(exp.status)}; background: {statusColor(exp.status)}22;"
									>
										{exp.status}
									</span>
								</div>
								{#if exp.hypothesis}
									<p class="mt-1 text-sm text-[#5e7282] line-clamp-1">{exp.hypothesis}</p>
								{/if}
							</div>
							<div class="ml-4 flex items-center gap-3 shrink-0">
								<span class="text-sm text-[#8a9baa]">{headlineEffect(analysis)}</span>
								{#if analysis}
									<ConfidenceBadge confidence={analysis.overall_confidence} />
								{/if}
							</div>
						</div>
					</button>
				{/each}
			</div>
		{:else}
			<div class="flex min-h-[40vh] flex-col items-center justify-center text-center">
				<p class="text-lg text-[#5e7282]">No experiments yet</p>
				<p class="mt-2 max-w-md text-sm text-[#4a5c6a]">
					Drop a <strong class="text-[#8a9baa]">.json</strong> experiment spec to start
					tracking how your interventions affect health metrics.
				</p>
				<button type="button" class="import-btn mt-4" onclick={openImportModal}>Import experiment</button>
			</div>
		{/if}
	</div>
{/if}

<!-- Import modal -->
{#if importModalOpen}
	<!-- svelte-ignore a11y_click_events_have_key_events a11y_no_static_element_interactions a11y_no_noninteractive_element_interactions a11y_interactive_supports_focus -->
	<div class="modal-backdrop" role="dialog" tabindex="-1" onclick={(e) => { if (e.target === e.currentTarget) closeImportModal(); }}>
		<div class="modal-panel">
			<div class="modal-header">
				<h2>Import Experiment</h2>
				<button type="button" class="modal-close" onclick={closeImportModal} title="Close">
					<svg viewBox="0 0 16 16" width="14" height="14" fill="none">
						<path d="M4 4L12 12M12 4L4 12" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
					</svg>
				</button>
			</div>

			{#if importStep === 'idle'}
				<!-- svelte-ignore a11y_click_events_have_key_events a11y_no_static_element_interactions a11y_no_noninteractive_element_interactions -->
				<div
					class="drop-zone"
					role="button"
					tabindex="0"
					ondrop={onDrop}
					ondragover={(e) => e.preventDefault()}
					onclick={() => fileInputEl?.click()}
				>
					<svg viewBox="0 0 24 24" width="32" height="32" fill="none">
						<path d="M12 16V4M12 4L8 8M12 4L16 8" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
						<path d="M20 16V18C20 19.1 19.1 20 18 20H6C4.9 20 4 19.1 4 18V16" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
					</svg>
					<span>Drop a <strong>.json</strong> experiment spec here or click to browse</span>
				</div>
				<input type="file" accept=".json" class="file-input-hidden" bind:this={fileInputEl} onchange={onFileInput} />
				{#if importError}
					<div class="import-error">{importError}</div>
				{/if}

			{:else if importStep === 'previewing'}
				<div class="import-status">Validating experiment...</div>

			{:else if importStep === 'preview-ok' && importPreview && importSpec}
				<div class="preview-summary">
					<div class="preview-name">{importSpec.name}</div>
					{#if importSpec.hypothesis}
						<div class="preview-hypothesis">{importSpec.hypothesis}</div>
					{/if}
					<div class="preview-stats">
						<span>{importSpec.outcome_metrics?.length ?? 0} outcome metrics</span>
						<span>{importSpec.confounder_watch?.length ?? 0} confounders</span>
						{#if importSpec.design}
							<span>{importSpec.design.expected_lag_days?.length ?? 1} lag offsets</span>
						{/if}
					</div>
					{#if importSpec.design}
						<div class="preview-dates">
							{#if importSpec.design.baseline_start_date && importSpec.design.baseline_end_date}
								<span>Baseline: {importSpec.design.baseline_start_date} to {importSpec.design.baseline_end_date}</span>
							{:else if importSpec.design.baseline_duration_days}
								<span>Baseline: {importSpec.design.baseline_duration_days} days before routine start</span>
							{/if}
							{#if importSpec.design.treatment_start_date}
								<span>Treatment: {importSpec.design.treatment_start_date}{importSpec.design.treatment_end_date ? ` to ${importSpec.design.treatment_end_date}` : ' (ongoing)'}</span>
							{:else}
								<span>Treatment: starts with linked routine</span>
							{/if}
						</div>
					{/if}
					{#if importPreview.issues.length > 0}
						<div class="issue-list">
							{#each importPreview.issues as issue}
								<div class="issue-row" class:warning={issue.level === 'warning'}>
									<span class="issue-level" class:error={issue.level === 'error'} class:warn={issue.level === 'warning'}>
										{issue.level}
									</span>
									<span>{issue.message}</span>
								</div>
							{/each}
						</div>
					{/if}
					{#if importError}
						<div class="import-error">{importError}</div>
					{/if}
				</div>
				<div class="modal-actions">
					<button type="button" class="action-btn primary" onclick={() => void handleImport()}>Import</button>
					<button type="button" class="action-btn ghost" onclick={closeImportModal}>Cancel</button>
				</div>

			{:else if importStep === 'preview-error' && importPreview}
				<div class="preview-summary">
					<div class="preview-name">{importSpec?.name ?? 'Experiment'}</div>
					<div class="issue-list">
						{#each importPreview.issues as issue}
							<div class="issue-row">
								<span class="issue-level" class:error={issue.level === 'error'} class:warn={issue.level === 'warning'}>
									{issue.level}
								</span>
								<span>{issue.message}</span>
							</div>
						{/each}
					</div>
				</div>
				<div class="modal-actions">
					<button type="button" class="action-btn ghost" onclick={resetImport}>Try another file</button>
					<button type="button" class="action-btn ghost" onclick={closeImportModal}>Cancel</button>
				</div>

			{:else if importStep === 'importing'}
				<div class="import-status">Importing and running initial analysis...</div>

			{:else if importStep === 'done' && importResult}
				<div class="preview-summary">
					<div class="import-success">Experiment imported</div>
					<div class="preview-name">{importResult.experiment.name}</div>
					{#if importResult.analysis}
						<div class="preview-stats">
							<span>{importResult.analysis.days_in_baseline}d baseline</span>
							<span>{importResult.analysis.days_in_treatment}d treatment</span>
							<span>Confidence: {importResult.analysis.overall_confidence}</span>
						</div>
					{/if}
				</div>
				<div class="modal-actions">
					<button type="button" class="action-btn primary" onclick={() => { closeImportModal(); if (importResult) selectExperiment(importResult.experiment.id); }}>View experiment</button>
					<button type="button" class="action-btn ghost" onclick={closeImportModal}>Done</button>
				</div>
			{/if}
		</div>
	</div>
{/if}

<style>
	.import-btn {
		font-family: 'DM Mono', monospace;
		font-size: 11px;
		letter-spacing: 0.08em;
		text-transform: uppercase;
		color: #5bb5a6;
		padding: 6px 12px;
		border-radius: 6px;
		border: 1px solid rgba(91, 181, 166, 0.25);
		background: transparent;
		cursor: pointer;
		transition: background 0.15s;
	}
	.import-btn:hover { background: rgba(91, 181, 166, 0.1); }

	/* ── Modal ── */
	.modal-backdrop {
		position: fixed;
		inset: 0;
		background: rgba(0, 0, 0, 0.6);
		display: flex;
		align-items: center;
		justify-content: center;
		z-index: 100;
	}

	.modal-panel {
		width: 520px;
		max-width: 90vw;
		max-height: 80vh;
		overflow-y: auto;
		border-radius: 14px;
		background: #1a2632;
		border: 1px solid rgba(255, 255, 255, 0.08);
		padding: 24px;
		display: flex;
		flex-direction: column;
		gap: 20px;
	}

	.modal-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
	}

	.modal-header h2 {
		margin: 0;
		font-family: 'Instrument Sans', sans-serif;
		font-size: 16px;
		font-weight: 600;
		color: #eef5f8;
	}

	.modal-close {
		width: 30px;
		height: 30px;
		border-radius: 6px;
		border: 1px solid rgba(255, 255, 255, 0.06);
		background: transparent;
		color: #6b8292;
		cursor: pointer;
		display: flex;
		align-items: center;
		justify-content: center;
		transition: background 0.15s, color 0.15s;
	}
	.modal-close:hover { background: rgba(255, 255, 255, 0.06); color: #c3d3dd; }

	.drop-zone {
		border: 2px dashed rgba(255, 255, 255, 0.12);
		border-radius: 12px;
		padding: 40px 20px;
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 12px;
		color: #6b8292;
		font-family: 'DM Mono', monospace;
		font-size: 12px;
		cursor: pointer;
		transition: border-color 0.2s, background 0.2s;
	}
	.drop-zone:hover { border-color: rgba(91, 181, 166, 0.4); background: rgba(91, 181, 166, 0.04); }
	.drop-zone strong { color: #c3d3dd; }

	.file-input-hidden { display: none; }

	.import-status {
		font-family: 'DM Mono', monospace;
		font-size: 12px;
		color: #8fa3b0;
		text-align: center;
		padding: 24px 0;
	}

	.import-error {
		font-family: 'DM Mono', monospace;
		font-size: 11px;
		color: #f2a399;
		padding: 8px 10px;
		border-radius: 8px;
		background: rgba(232, 93, 74, 0.08);
		margin-top: 4px;
	}

	.preview-summary {
		display: flex;
		flex-direction: column;
		gap: 12px;
	}

	.preview-name {
		font-family: 'Instrument Sans', sans-serif;
		font-size: 14px;
		font-weight: 600;
		color: #eef5f8;
	}

	.preview-hypothesis {
		font-size: 13px;
		color: #8fa3b0;
		font-style: italic;
	}

	.preview-stats {
		display: flex;
		gap: 12px;
		font-family: 'DM Mono', monospace;
		font-size: 11px;
		color: #6b8292;
	}

	.preview-dates {
		display: flex;
		flex-direction: column;
		gap: 2px;
		font-family: 'DM Mono', monospace;
		font-size: 11px;
		color: #6b8292;
	}

	.issue-list {
		display: flex;
		flex-direction: column;
		gap: 4px;
		max-height: 200px;
		overflow-y: auto;
	}

	.issue-row {
		display: flex;
		align-items: flex-start;
		gap: 8px;
		padding: 6px 8px;
		border-radius: 6px;
		background: rgba(232, 93, 74, 0.06);
		font-size: 12px;
		color: #b8c8d4;
	}
	.issue-row.warning {
		background: rgba(212, 148, 76, 0.06);
	}

	.issue-level {
		flex-shrink: 0;
		padding: 1px 6px;
		border-radius: 3px;
		font-family: 'DM Mono', monospace;
		font-size: 10px;
		text-transform: uppercase;
		letter-spacing: 0.08em;
	}
	.issue-level.error { background: rgba(232, 93, 74, 0.15); color: #E85D4A; }
	.issue-level.warn { background: rgba(212, 148, 76, 0.15); color: #D4944C; }

	.import-success {
		font-family: 'Instrument Sans', sans-serif;
		font-size: 14px;
		font-weight: 600;
		color: #5bb5a6;
	}

	.modal-actions {
		display: flex;
		gap: 8px;
	}

	.action-btn {
		padding: 8px 16px;
		border-radius: 8px;
		font-family: 'DM Mono', monospace;
		font-size: 11px;
		letter-spacing: 0.06em;
		cursor: pointer;
		transition: background 0.15s;
	}

	.action-btn.primary {
		background: rgba(91, 181, 166, 0.15);
		border: 1px solid rgba(91, 181, 166, 0.3);
		color: #5bb5a6;
	}
	.action-btn.primary:hover { background: rgba(91, 181, 166, 0.25); }

	.action-btn.ghost {
		background: transparent;
		border: 1px solid rgba(255, 255, 255, 0.08);
		color: #8fa3b0;
	}
	.action-btn.ghost:hover { background: rgba(255, 255, 255, 0.04); }
</style>
