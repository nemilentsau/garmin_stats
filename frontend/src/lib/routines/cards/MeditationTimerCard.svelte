<script lang="ts">
	/**
	 * MeditationTimerCard — dedicated card for meditation_timer payloads.
	 *
	 * view mode: static summary showing technique, anchor, duration, and instructions.
	 * log mode: same header info plus per-prompt rating inputs. Emits TimerActual on
	 * every rating change/blur. No breathing animation (meditation has no phase sequence).
	 *
	 * Animation is explicitly omitted: meditation cards have no phase sequence to drive.
	 * No statistical computation happens here.
	 */
	import { untrack } from 'svelte';
	import type { ScheduleOccurrence, TodayCard } from '$lib/api';
	import { buildInitialRatings, cleanRatings } from './rating-helpers.js';
	import RatingsGrid from './RatingsGrid.svelte';

	type MeditationPayload = Extract<
		ScheduleOccurrence['payload_json'],
		{ card_type: 'meditation_timer' }
	>;
	type FullActual = TodayCard['actual_json'];
	export type TimerActual = {
		card_type: 'meditation_timer';
		ratings: Record<string, number>;
	};

	let {
		card,
		mode,
		onActual
	}: {
		card: { payload_json: MeditationPayload; actual_json?: FullActual };
		mode: 'log' | 'view';
		onActual?: (actual: TimerActual) => void;
	} = $props();

	const payload = $derived(card.payload_json);
	const prompts = $derived(payload.rating_prompts ?? []);

	// ── One-time synchronous init — never re-runs when actual_json changes ────
	// The component is freshly mounted each time a detail panel opens ({#if isExpanded}),
	// so reading card.actual_json once at construction via untrack is correct and sufficient.
	// A reactive $effect would re-seed ratings on every debounced persist, wiping
	// in-progress input (e.g. a second rating typed within the debounce window).
	const initialActual = untrack(() =>
		card.actual_json?.card_type === 'meditation_timer' ? card.actual_json : null
	);
	const initialPrompts = untrack(() => card.payload_json.rating_prompts ?? []);

	// ── Ratings state ─────────────────────────────────────────────────────────
	let ratings = $state<Record<string, number | null>>(
		buildInitialRatings(initialPrompts, initialActual?.ratings)
	);

	function emit() {
		onActual?.({
			card_type: 'meditation_timer',
			ratings: cleanRatings(ratings)
		});
	}

	/** Humanize snake_case technique names: "focused_attention" → "Focused attention". */
	function humanizeTechnique(technique: string): string {
		const s = technique.replace(/_/g, ' ');
		return s.charAt(0).toUpperCase() + s.slice(1);
	}
</script>

{#if payload.instructions}
	<p class="detail-copy">{payload.instructions}</p>
{/if}

<!-- Technique + anchor + duration meta row -->
<div class="meta-row">
	<span class="badge">{humanizeTechnique(payload.technique)}</span>
	{#if payload.anchor}
		<span class="anchor-label">{payload.anchor}</span>
	{/if}
	<span class="duration-label">{payload.duration_minutes} min</span>
</div>

{#if mode === 'log'}
	<RatingsGrid {prompts} bind:ratings onCommit={emit} />
{/if}

<style>
	.detail-copy {
		margin: 0;
		color: #a7bac6;
		font-size: 13px;
		line-height: 1.5;
	}

	/* Meta row: technique badge + anchor + duration */
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
		background: rgba(126, 94, 217, 0.12);
		border: 1px solid rgba(126, 94, 217, 0.25);
		color: #9b7be0;
		font-family: 'DM Mono', monospace;
		font-size: 11px;
		letter-spacing: 0.06em;
	}

	.anchor-label {
		color: #8fa3b0;
		font-size: 12px;
		font-style: italic;
	}

	.duration-label {
		color: #6b8292;
		font-size: 12px;
		font-family: 'DM Mono', monospace;
		letter-spacing: 0.08em;
	}
</style>
