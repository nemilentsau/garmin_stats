<script lang="ts">
	/**
	 * BreathTimerCard — dedicated card for breath_timer payloads.
	 *
	 * view mode: static reference showing pattern_label, duration_minutes, and instructions.
	 * log mode: same reference + a single 3-level segmented "How much did you downshift?"
	 * control (Barely / Somewhat / Strongly → 1 / 2 / 3). Emits TimerActual on every tap.
	 *
	 * No animation, timer, phase countdown, or cycle tracking. The backend payload carries
	 * no phases, rating_prompts, or completed_cycles; this card matches that contract exactly.
	 */
	import { untrack } from 'svelte';
	import type { ScheduleOccurrence, TodayCard } from '$lib/api';

	type BreathPayload = Extract<ScheduleOccurrence['payload_json'], { card_type: 'breath_timer' }>;
	type FullActual = TodayCard['actual_json'];
	export type TimerActual = {
		card_type: 'breath_timer';
		ratings: { felt_downshift?: 1 | 2 | 3 };
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

	// ── One-time synchronous init — never re-runs when actual_json changes ────
	// The component is freshly mounted each time a detail panel opens ({#if isExpanded}),
	// so reading card.actual_json once at construction via untrack is correct and sufficient.
	// A reactive $effect would re-seed felt_downshift on every debounced persist, wiping
	// an in-progress tap within the debounce window.
	let feltDownshift = $state<1 | 2 | 3 | null>(
		untrack(() => {
			const a = card.actual_json;
			if (a?.card_type === 'breath_timer') {
				const v = a.ratings?.felt_downshift;
				if (v === 1 || v === 2 || v === 3) return v;
			}
			return null;
		})
	);

	function emit() {
		onActual?.({
			card_type: 'breath_timer',
			ratings: feltDownshift == null ? {} : { felt_downshift: feltDownshift }
		});
	}

	function selectLevel(level: 1 | 2 | 3) {
		// Re-tapping the selected level clears it — an accidental tap must not
		// permanently record a fabricated downshift rating.
		feltDownshift = feltDownshift === level ? null : level;
		emit();
	}

	const LEVELS: { value: 1 | 2 | 3; label: string }[] = [
		{ value: 1, label: 'Barely' },
		{ value: 2, label: 'Somewhat' },
		{ value: 3, label: 'Strongly' }
	];
</script>

{#if payload.instructions}
	<p class="detail-copy">{payload.instructions}</p>
{/if}

<div class="meta-row">
	<span class="badge">{payload.pattern_label}</span>
	<span class="duration-label">{payload.duration_minutes} min</span>
</div>

{#if mode === 'log'}
	<div class="downshift-section">
		<span class="section-label">How much did you downshift?</span>
		<div class="segment-row" role="group" aria-label="Downshift level">
			{#each LEVELS as lvl}
				<button
					class="seg-btn"
					class:selected={feltDownshift === lvl.value}
					onclick={() => selectLevel(lvl.value)}
					aria-pressed={feltDownshift === lvl.value}
				>
					{lvl.label}
				</button>
			{/each}
		</div>
	</div>
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

	/* Downshift segmented control (log mode only) */
	.downshift-section {
		display: flex;
		flex-direction: column;
		gap: 8px;
	}

	.section-label {
		font-family: 'DM Mono', monospace;
		font-size: 10px;
		letter-spacing: 0.14em;
		text-transform: uppercase;
		color: #8fa3b0;
	}

	.segment-row {
		display: flex;
		gap: 0;
		border-radius: 8px;
		overflow: hidden;
		border: 1px solid rgba(74, 144, 217, 0.25);
		width: fit-content;
	}

	.seg-btn {
		padding: 7px 18px;
		border: none;
		border-right: 1px solid rgba(74, 144, 217, 0.2);
		background: rgba(74, 144, 217, 0.05);
		color: #6b8292;
		font: inherit;
		font-size: 12px;
		font-family: 'DM Mono', monospace;
		letter-spacing: 0.05em;
		cursor: pointer;
		transition:
			background 0.15s,
			color 0.15s;
		white-space: nowrap;
	}

	.seg-btn:last-child {
		border-right: none;
	}

	.seg-btn:hover:not(.selected) {
		background: rgba(74, 144, 217, 0.12);
		color: #a7bac6;
	}

	.seg-btn.selected {
		background: rgba(74, 144, 217, 0.22);
		color: #4a90d9;
	}
</style>
