<script lang="ts">
	/**
	 * BreathTimerCard — dedicated card for breath_timer payloads.
	 *
	 * view mode: static phase sequence, pattern label, duration, instructions.
	 * log mode: CSS-driven breathing animation cycling through payload.phases, start/pause
	 * control with current-phase label and per-second countdown, rating inputs, and an
	 * optional completed_cycles field. Emits TimerActual on every rating or cycles change.
	 *
	 * Animation is purely presentational: CSS transform transitions driven by a Svelte
	 * setInterval tick. No statistical computation happens here.
	 */
	import type { ScheduleOccurrence, TodayCard } from '$lib/api';

	type BreathPayload = Extract<ScheduleOccurrence['payload_json'], { card_type: 'breath_timer' }>;
	type FullActual = TodayCard['actual_json'];
	export type TimerActual = {
		card_type: 'breath_timer';
		ratings: Record<string, number>;
		completed_cycles: number | null;
	};

	let {
		card,
		mode,
		onActual
	}: {
		card: { payload_json: BreathPayload; actual_json?: FullActual };
		mode: 'log' | 'view';
		onActual?: (actual: TimerActual) => void;
	} = $props();

	const payload = $derived(card.payload_json);
	const phases = $derived(payload.phases ?? []);
	const prompts = $derived(payload.rating_prompts ?? []);

	const existingActual = $derived(
		card.actual_json?.card_type === 'breath_timer' ? card.actual_json : null
	);

	// ── Ratings state ─────────────────────────────────────────────────────────
	let ratings = $state<Record<string, number | null>>({});
	let completedCycles = $state<number | null>(null);

	// Seed from persisted actual whenever the card identity changes.
	$effect(() => {
		for (const p of prompts) {
			ratings[p.key] = existingActual?.ratings?.[p.key] ?? null;
		}
		completedCycles = existingActual?.completed_cycles ?? null;
	});

	function emit() {
		const clean: Record<string, number> = {};
		for (const [k, v] of Object.entries(ratings)) {
			if (typeof v === 'number') clean[k] = v;
		}
		onActual?.({
			card_type: 'breath_timer',
			ratings: clean,
			completed_cycles: completedCycles ?? null
		});
	}

	// ── Animation state (log mode only) ───────────────────────────────────────
	let running = $state(false);
	let phaseIdx = $state(0);
	let secondsLeft = $state(0);
	let cyclesDone = $state(0);

	// Drives the CSS transition. `expanded` controls the scale; `circleDuration`
	// is the CSS transition-duration (matches the inhale/exhale phase seconds so
	// the circle grows/shrinks over exactly the right interval).
	let expanded = $state(false);
	let circleDuration = $state(0);

	let timerId: ReturnType<typeof setInterval> | null = null;

	const PHASE_LABELS: Record<string, string> = {
		inhale: 'Inhale',
		hold_full: 'Hold',
		exhale: 'Exhale',
		hold_empty: 'Hold'
	};

	/**
	 * Apply visual + countdown state for the given phase index.
	 * inhale → expand over phase.seconds; exhale → contract over phase.seconds.
	 * hold_* → snap (very short duration) and maintain current scale.
	 */
	function applyPhase(idx: number) {
		const phase = phases[idx];
		if (!phase) return;
		secondsLeft = phase.seconds;
		if (phase.kind === 'inhale') {
			circleDuration = phase.seconds;
			expanded = true;
		} else if (phase.kind === 'exhale') {
			circleDuration = phase.seconds;
			expanded = false;
		} else if (phase.kind === 'hold_full') {
			circleDuration = 0.1;
			expanded = true;
		} else {
			// hold_empty
			circleDuration = 0.1;
			expanded = false;
		}
	}

	function tick() {
		secondsLeft -= 1;
		if (secondsLeft <= 0) {
			const next = (phaseIdx + 1) % phases.length;
			if (next === 0) cyclesDone += 1;
			phaseIdx = next;
			applyPhase(next);
		}
	}

	function toggleRunning() {
		if (running) {
			if (timerId) clearInterval(timerId);
			timerId = null;
			running = false;
		} else {
			if (phases.length === 0) return;
			running = true;
			applyPhase(phaseIdx);
			timerId = setInterval(tick, 1000);
		}
	}

	// Cleanup the interval when the component is destroyed.
	$effect(() => {
		return () => {
			if (timerId) clearInterval(timerId);
		};
	});

	const currentPhase = $derived(phases[phaseIdx]);
	const currentLabel = $derived(currentPhase ? (PHASE_LABELS[currentPhase.kind] ?? currentPhase.kind) : '');
</script>

{#if payload.instructions}
	<p class="detail-copy">{payload.instructions}</p>
{/if}

{#if mode === 'view'}
	<!-- Static summary for schedule/view mode -->
	<div class="meta-row">
		<span class="badge">{payload.pattern_label}</span>
		<span class="duration-label">{payload.duration_minutes} min</span>
	</div>

	{#if phases.length > 0}
		<div class="phase-list">
			{#each phases as phase}
				<div class="phase-row">
					<span class="phase-kind">{PHASE_LABELS[phase.kind] ?? phase.kind}</span>
					<span class="phase-secs">{phase.seconds}s</span>
				</div>
			{/each}
		</div>
	{/if}
{:else}
	<!-- Log mode: animation + ratings -->
	<div class="meta-row">
		<span class="badge">{payload.pattern_label}</span>
		<span class="duration-label">{payload.duration_minutes} min</span>
	</div>

	<!-- Breathing animation -->
	{#if phases.length > 0}
		<div class="anim-wrapper">
			<div class="phase-label" class:running>
				{#if running}
					{currentLabel}
				{:else}
					Ready
				{/if}
			</div>

			<div
				class="breath-circle"
				class:expanded
				style="--dur: {circleDuration}s"
			></div>

			<div class="countdown">
				{#if running}
					{secondsLeft}s
				{:else if cyclesDone > 0}
					{cyclesDone} {cyclesDone === 1 ? 'cycle' : 'cycles'}
				{:else}
					&nbsp;
				{/if}
			</div>

			<button class="start-btn" onclick={toggleRunning}>
				{running ? 'Pause' : cyclesDone > 0 ? 'Resume' : 'Start'}
			</button>
		</div>
	{/if}

	<!-- Ratings -->
	{#if prompts.length > 0}
		<div class="ratings-section">
			<div class="ratings-grid">
				{#each prompts as prompt}
					<label class="detail-field">
						<span class="field-label">{prompt.label}</span>
						<input
							type="number"
							bind:value={ratings[prompt.key]}
							min={prompt.scale_min}
							max={prompt.scale_max}
							placeholder="{prompt.scale_min}–{prompt.scale_max}"
							onchange={emit}
							onblur={emit}
						/>
					</label>
				{/each}
			</div>
		</div>
	{/if}

	<!-- Optional completed cycles override -->
	<label class="detail-field cycles-field">
		<span class="field-label">Completed cycles</span>
		<input
			type="number"
			bind:value={completedCycles}
			min={0}
			placeholder="optional"
			onchange={emit}
			onblur={emit}
		/>
	</label>
{/if}

<style>
	.detail-copy {
		margin: 0;
		color: #a7bac6;
		font-size: 13px;
		line-height: 1.5;
	}

	/* Meta row: pattern badge + duration */
	.meta-row {
		display: flex;
		align-items: center;
		gap: 10px;
		flex-wrap: wrap;
	}

	.badge {
		display: inline-block;
		padding: 3px 8px;
		border-radius: 5px;
		background: rgba(74, 144, 217, 0.12);
		border: 1px solid rgba(74, 144, 217, 0.25);
		color: #4a90d9;
		font-family: 'DM Mono', monospace;
		font-size: 11px;
		letter-spacing: 0.06em;
	}

	.duration-label {
		color: #6b8292;
		font-size: 12px;
		font-family: 'DM Mono', monospace;
		letter-spacing: 0.08em;
	}

	/* Phase list (view mode) */
	.phase-list {
		display: grid;
		gap: 4px;
	}

	.phase-row {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 6px 10px;
		border-radius: 6px;
		background: rgba(255, 255, 255, 0.03);
		font-size: 12px;
	}

	.phase-kind {
		color: #c5d8e4;
		font-size: 12px;
	}

	.phase-secs {
		color: #6b8292;
		font-family: 'DM Mono', monospace;
		font-size: 11px;
	}

	/* Animation area (log mode) */
	.anim-wrapper {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 10px;
		padding: 12px 0 4px;
	}

	.phase-label {
		font-family: 'DM Mono', monospace;
		font-size: 11px;
		letter-spacing: 0.14em;
		text-transform: uppercase;
		color: #6b8292;
		height: 16px;
		transition: color 0.3s ease;
	}

	.phase-label.running {
		color: #4a90d9;
	}

	/* The breathing circle */
	.breath-circle {
		width: 72px;
		height: 72px;
		border-radius: 50%;
		border: 2px solid rgba(74, 144, 217, 0.4);
		background: radial-gradient(circle, rgba(74, 144, 217, 0.08) 0%, rgba(74, 144, 217, 0.02) 100%);
		transform: scale(1);
		transition: transform var(--dur, 0s) ease-in-out,
			box-shadow var(--dur, 0s) ease-in-out,
			border-color var(--dur, 0s) ease-in-out;
		box-shadow: 0 0 0 0 rgba(74, 144, 217, 0);
	}

	.breath-circle.expanded {
		transform: scale(1.65);
		border-color: rgba(74, 144, 217, 0.7);
		box-shadow: 0 0 20px 4px rgba(74, 144, 217, 0.15);
	}

	.countdown {
		font-family: 'DM Mono', monospace;
		font-size: 13px;
		color: #6b8292;
		height: 18px;
		letter-spacing: 0.08em;
	}

	.start-btn {
		padding: 7px 24px;
		border-radius: 8px;
		border: 1px solid rgba(74, 144, 217, 0.35);
		background: rgba(74, 144, 217, 0.08);
		color: #4a90d9;
		font: inherit;
		font-size: 12px;
		font-family: 'DM Mono', monospace;
		letter-spacing: 0.08em;
		cursor: pointer;
		transition: background 0.15s, border-color 0.15s;
	}

	.start-btn:hover {
		background: rgba(74, 144, 217, 0.15);
		border-color: rgba(74, 144, 217, 0.55);
	}

	/* Ratings */
	.ratings-section {
		margin-top: 4px;
	}

	.ratings-grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
		gap: 8px;
	}

	.cycles-field {
		margin-top: 4px;
	}

	.detail-field {
		display: flex;
		flex-direction: column;
		gap: 6px;
	}

	.field-label {
		font-family: 'DM Mono', monospace;
		font-size: 10px;
		letter-spacing: 0.14em;
		text-transform: uppercase;
		color: #8fa3b0;
	}

	input[type='number'] {
		border: 1px solid rgba(255, 255, 255, 0.1);
		background: rgba(8, 15, 24, 0.7);
		color: #eef5f8;
		border-radius: 8px;
		padding: 8px 10px;
		font: inherit;
		font-size: 13px;
		width: 100%;
		box-sizing: border-box;
	}
</style>
