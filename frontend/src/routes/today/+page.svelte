<script lang="ts">
	import { api, type Program } from '$lib/api';

	// --- State ---
	let program = $state<Program | null>(null);
	let loading = $state(true);
	let error = $state<string | null>(null);

	// User selections
	let dayType = $state<string>('easy_recovery');
	let coreDay = $state<string>('A');

	// --- Derived from spec ---
	type Protocol = Record<string, unknown>;
	type DayTemplate = Record<string, unknown>;
	type StretchTemplate = { label: string; duration_min: number; exercises: string[] };
	type SlotRef = { protocol_id: string; duration_min: number; optional?: boolean; selection_rule?: string };

	const spec = $derived(program?.spec as Record<string, unknown> | null);
	const protocols = $derived<Protocol[]>((spec?.protocols as Protocol[]) ?? []);
	const dayTemplates = $derived<Record<string, DayTemplate>>((spec?.day_templates as Record<string, DayTemplate>) ?? {});
	const stretchTemplates = $derived<Record<string, StretchTemplate>>((spec?.stretch_templates as Record<string, StretchTemplate>) ?? {});
	const supportingBlocks = $derived<Record<string, { label: string; exercises: string[] }>>((spec?.supporting_blocks as Record<string, { label: string; exercises: string[] }>) ?? {});

	const template = $derived(dayTemplates[dayType] ?? null);
	const stretchKey = $derived((template?.stretch_template as string) ?? '');
	const stretch = $derived(stretchTemplates[stretchKey] ?? null);
	const coreDose = $derived((template?.core_dose as string) ?? 'full');
	const supportBlockNums = $derived<string[]>((template?.supporting_blocks as string[]) ?? []);

	// Lookup helpers
	function getProtocol(id: string): Protocol | undefined {
		return protocols.find((p) => p.id === id);
	}

	function getCoreExercises(): Protocol[] {
		return protocols.filter((p) => p.type === 'core' && p.rotation_day === coreDay);
	}

	function getSupportExercises(blockNum: string): Protocol[] {
		const block = supportingBlocks[blockNum];
		if (!block) return [];
		return block.exercises.map((id: string) => getProtocol(id)).filter(Boolean) as Protocol[];
	}

	function doseLabel(p: Protocol): string {
		if (coreDose === 'reduced' || coreDose === 'activation') {
			return (p.reduced_dose as string) ?? (p.full_dose as string) ?? '';
		}
		return (p.full_dose as string) ?? '';
	}

	// Day type options
	const dayTypes = [
		{ key: 'hard_training', label: 'Hard Training', short: 'Hard' },
		{ key: 'easy_recovery', label: 'Easy / Recovery', short: 'Easy' },
		{ key: 'rest_day', label: 'Rest Day', short: 'Rest' },
		{ key: 'pre_performance', label: 'Pre-Performance', short: 'Pre-Perf' },
		{ key: 'travel', label: 'Travel', short: 'Travel' }
	];

	const coreDays = ['A', 'B', 'C', 'D'];

	// --- Load ---
	async function loadActiveProgram() {
		loading = true;
		error = null;
		try {
			const res = await api.getPrograms('active');
			if (res.programs.length === 0) {
				program = null;
			} else {
				// Load full program with spec
				program = await api.getProgram(res.programs[0].id);
			}
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to load program';
		} finally {
			loading = false;
		}
	}

	$effect(() => {
		loadActiveProgram();
	});
</script>

<svelte:head>
	<title>Today - Garmin Stats</title>
</svelte:head>

<div class="today-page">
	{#if loading}
		<p class="status-msg">Loading program...</p>
	{:else if error}
		<p class="status-msg error">{error}</p>
	{:else if !program}
		<div class="empty-state">
			<p class="empty-title">No active program</p>
			<p class="empty-desc">Import a program spec on the <a href="/programs">Programs</a> page to get started.</p>
		</div>
	{:else}
		<!-- Control bar -->
		<div class="control-bar">
			<div class="control-group">
				<span class="control-label">DAY TYPE</span>
				<div class="control-pills">
					{#each dayTypes as dt}
						<button
							class="pill"
							class:active={dayType === dt.key}
							onclick={() => (dayType = dt.key)}
						>{dt.short}</button>
					{/each}
				</div>
			</div>
			<div class="control-group">
				<span class="control-label">CORE ROTATION</span>
				<div class="control-pills">
					{#each coreDays as cd}
						<button
							class="pill core-pill"
							class:active={coreDay === cd}
							onclick={() => (coreDay = cd)}
						>{cd}</button>
					{/each}
				</div>
			</div>
		</div>

		<!-- Day summary -->
		{#if template}
			<div class="day-summary">
				<span class="summary-chip">{(template.label as string) ?? dayType}</span>
				<span class="summary-priority">{(template.priority as string) ?? ''}</span>
			</div>
		{/if}

		<!-- Morning Stack -->
		<section class="stack-section">
			<h2 class="section-title">
				<span class="section-icon">&#x2600;</span>
				Morning Stack
			</h2>

			<!-- Stretching -->
			{#if stretch}
				<div class="block">
					<div class="block-header">
						<span class="block-label">STRETCH</span>
						<span class="block-detail">{stretch.label} &mdash; ~{stretch.duration_min} min</span>
					</div>
					<div class="exercise-list">
						{#each stretch.exercises as exId}
							{@const ex = getProtocol(exId)}
							{#if ex}
								<div class="exercise-row">
									<span class="ex-id">{ex.id}</span>
									<span class="ex-name">{ex.name}</span>
									<span class="ex-dose">
										{#if ex.default_hold_sec}
											{ex.default_hold_sec}s{ex.per_side ? ' ea side' : ''}
										{:else if ex.default_reps}
											{ex.default_reps} reps
										{/if}
									</span>
								</div>
							{/if}
						{/each}
					</div>
				</div>
			{/if}

			<!-- Breathwork -->
			{#if template?.morning_breathwork}
				{@const bw = template.morning_breathwork as SlotRef}
				{@const protocol = getProtocol(bw.protocol_id)}
				{#if protocol}
					<div class="block">
						<div class="block-header">
							<span class="block-label">BREATHWORK</span>
							<span class="block-detail">{bw.duration_min} min</span>
						</div>
						<div class="exercise-list">
							<div class="exercise-row">
								<span class="ex-name">{protocol.name}</span>
								<span class="ex-dose">{protocol.pattern ?? ''}</span>
							</div>
						</div>
					</div>
				{/if}
			{/if}

			<!-- Core -->
			{#if getCoreExercises().length > 0}
			{@const coreExercises = getCoreExercises()}
				<div class="block">
					<div class="block-header">
						<span class="block-label">CORE &mdash; Day {coreDay}</span>
						<span class="block-detail">{coreDose === 'reduced' ? 'Reduced dose' : coreDose === 'activation' ? 'Activation only' : 'Full dose'}</span>
					</div>
					<div class="exercise-list">
						{#each coreExercises as ex}
							<div class="exercise-row">
								<span class="ex-name">{ex.name}</span>
								<span class="ex-dose">{doseLabel(ex)}</span>
							</div>
						{/each}
					</div>
				</div>
			{/if}

			<!-- Supporting -->
			{#if supportBlockNums.length > 0}
				{#each supportBlockNums as blockNum}
					{@const blockDef = supportingBlocks[String(blockNum)]}
					{@const exercises = getSupportExercises(String(blockNum))}
					{#if blockDef && exercises.length > 0}
						<div class="block">
							<div class="block-header">
								<span class="block-label">SUPPORTING &mdash; Block {blockNum}</span>
								<span class="block-detail">{blockDef.label}</span>
							</div>
							<div class="exercise-list">
								{#each exercises as ex}
									<div class="exercise-row">
										<span class="ex-name">{ex.name}</span>
										<span class="ex-dose">{ex.dose ?? ''}</span>
									</div>
								{/each}
							</div>
						</div>
					{/if}
				{/each}
			{/if}
		</section>

		<!-- Midday -->
		{#if template?.midday}
			{@const mid = template.midday as SlotRef}
			{@const midProtocol = getProtocol(mid.protocol_id)}
			{#if midProtocol}
				<section class="stack-section">
					<h2 class="section-title">
						<span class="section-icon">&#x2601;</span>
						Midday
						{#if mid.optional}<span class="optional-tag">optional</span>{/if}
					</h2>
					<div class="block">
						<div class="exercise-list">
							<div class="exercise-row">
								<span class="ex-name">{midProtocol.name}</span>
								<span class="ex-dose">{mid.duration_min} min</span>
							</div>
						</div>
					</div>
				</section>
			{/if}
		{/if}

		<!-- Evening -->
		{#if template?.evening}
			{@const eve = template.evening as SlotRef}
			{@const eveProtocol = getProtocol(eve.protocol_id)}
			{#if eveProtocol}
				<section class="stack-section">
					<h2 class="section-title">
						<span class="section-icon">&#x263D;</span>
						Evening
					</h2>
					<div class="block">
						<div class="exercise-list">
							<div class="exercise-row">
								<span class="ex-name">{eveProtocol.name}</span>
								<span class="ex-dose">{eve.duration_min} min</span>
							</div>
							{#if eve.selection_rule}
								<p class="selection-rule">{eve.selection_rule}</p>
							{/if}
						</div>
					</div>
				</section>
			{/if}
		{/if}
	{/if}
</div>

<style>
	.today-page {
		display: flex;
		flex-direction: column;
		gap: 16px;
		max-width: 800px;
	}

	.status-msg {
		font-family: 'DM Mono', monospace;
		font-size: 12px;
		color: #5e7282;
		padding: 32px 0;
		text-align: center;
	}

	.status-msg.error {
		color: #e06b6b;
	}

	.empty-state {
		text-align: center;
		padding: 48px 0;
	}

	.empty-title {
		font-family: 'Instrument Sans', sans-serif;
		font-size: 18px;
		font-weight: 600;
		color: #8fa3b0;
		margin: 0 0 8px 0;
	}

	.empty-desc {
		font-family: 'DM Mono', monospace;
		font-size: 12px;
		color: #5e7282;
		margin: 0;
	}

	.empty-desc a {
		color: #5BB5A6;
		text-decoration: none;
	}

	.empty-desc a:hover {
		text-decoration: underline;
	}

	/* Control bar */
	.control-bar {
		display: flex;
		gap: 24px;
		align-items: flex-end;
		flex-wrap: wrap;
		padding: 12px 16px;
		background: rgba(255, 255, 255, 0.02);
		border: 1px solid rgba(255, 255, 255, 0.06);
		border-radius: 8px;
	}

	.control-group {
		display: flex;
		flex-direction: column;
		gap: 6px;
	}

	.control-label {
		font-family: 'DM Mono', monospace;
		font-size: 10px;
		letter-spacing: 1.5px;
		color: #4a5e6d;
	}

	.control-pills {
		display: flex;
		gap: 3px;
	}

	.pill {
		font-family: 'DM Mono', monospace;
		font-size: 11px;
		padding: 4px 10px;
		border-radius: 4px;
		border: none;
		background: transparent;
		color: #4a5e6d;
		cursor: pointer;
		transition: all 0.15s;
	}

	.pill:hover {
		color: #8fa3b0;
		background: rgba(255, 255, 255, 0.03);
	}

	.pill.active {
		color: #5BB5A6;
		background: rgba(91, 181, 166, 0.1);
	}

	.core-pill {
		min-width: 32px;
		text-align: center;
	}

	/* Day summary */
	.day-summary {
		display: flex;
		align-items: center;
		gap: 12px;
	}

	.summary-chip {
		font-family: 'Instrument Sans', sans-serif;
		font-size: 14px;
		font-weight: 600;
		color: #e8f0f5;
	}

	.summary-priority {
		font-family: 'DM Mono', monospace;
		font-size: 11px;
		color: #5e7282;
	}

	/* Stack sections */
	.stack-section {
		background: rgba(255, 255, 255, 0.02);
		border: 1px solid rgba(255, 255, 255, 0.06);
		border-radius: 8px;
		overflow: hidden;
	}

	.section-title {
		font-family: 'Instrument Sans', sans-serif;
		font-size: 14px;
		font-weight: 600;
		color: #e8f0f5;
		margin: 0;
		padding: 12px 16px;
		border-bottom: 1px solid rgba(255, 255, 255, 0.04);
		display: flex;
		align-items: center;
		gap: 8px;
	}

	.section-icon {
		font-size: 16px;
		opacity: 0.7;
	}

	.optional-tag {
		font-family: 'DM Mono', monospace;
		font-size: 10px;
		color: #5e7282;
		background: rgba(255, 255, 255, 0.04);
		padding: 2px 6px;
		border-radius: 3px;
		margin-left: auto;
	}

	/* Blocks within sections */
	.block {
		border-bottom: 1px solid rgba(255, 255, 255, 0.03);
	}

	.block:last-child {
		border-bottom: none;
	}

	.block-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 10px 16px;
		background: rgba(255, 255, 255, 0.015);
	}

	.block-label {
		font-family: 'DM Mono', monospace;
		font-size: 10px;
		letter-spacing: 1.5px;
		color: #5BB5A6;
	}

	.block-detail {
		font-family: 'DM Mono', monospace;
		font-size: 11px;
		color: #5e7282;
	}

	/* Exercise list */
	.exercise-list {
		padding: 4px 0;
	}

	.exercise-row {
		display: flex;
		align-items: center;
		gap: 10px;
		padding: 6px 16px;
		transition: background 0.1s;
	}

	.exercise-row:hover {
		background: rgba(255, 255, 255, 0.02);
	}

	.ex-id {
		font-family: 'DM Mono', monospace;
		font-size: 10px;
		color: #4a5e6d;
		min-width: 28px;
	}

	.ex-name {
		font-family: 'Instrument Sans', sans-serif;
		font-size: 13px;
		color: #c8d6e0;
		flex: 1;
	}

	.ex-dose {
		font-family: 'DM Mono', monospace;
		font-size: 11px;
		color: #5e7282;
		text-align: right;
		white-space: nowrap;
	}

	.selection-rule {
		font-family: 'DM Mono', monospace;
		font-size: 11px;
		color: #5e7282;
		padding: 4px 16px 8px;
		margin: 0;
		font-style: italic;
	}
</style>
