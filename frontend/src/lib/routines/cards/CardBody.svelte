<script lang="ts">
	/**
	 * CardBody — dispatches to the card-type-specific component for a single occurrence.
	 *
	 * Currently wired:
	 *   checklist → ChecklistCard (Phase 2)
	 *   all other types → TEMPORARY inline fallback, replaced in Phases 3-5
	 *
	 * Props:
	 *   card   — ScheduleOccurrence or TodayCard shape (both have payload_json; TodayCard adds
	 *            actual_json for pre-fill).
	 *   mode   — 'log' (Today board, user can enter actuals) | 'view' (Schedule, read-only).
	 *   onActual — callback fired whenever the user changes log state; only used in 'log' mode.
	 *              The parent is responsible for stashing + persisting the emitted value.
	 */
	import { untrack } from 'svelte';
	import type { ScheduleOccurrence, TodayCard } from '$lib/api';
	import ChecklistCard from './ChecklistCard.svelte';

	type CardPayload = ScheduleOccurrence['payload_json'];
	type CardActual = NonNullable<TodayCard['actual_json']>;

	let {
		card,
		mode,
		onActual
	}: {
		card: {
			name: string;
			summary?: string | null;
			payload_json: CardPayload;
			actual_json?: TodayCard['actual_json'];
		};
		mode: 'log' | 'view';
		onActual?: (actual: CardActual) => void;
	} = $props();

	// --- TEMPORARY fallback state: ratings for timer/strength cards ---
	// Each of these is replaced by a dedicated component in Phases 3-5.
	let ratings = $state<Record<string, number | null>>({});

	// Initialise fallback rating state from existing actual on mount.
	// CardBody is freshly mounted each time a detail panel opens, so capturing the initial prop
	// value here is intentional — untrack() makes that explicit to the Svelte compiler.
	const p = untrack(() => card.payload_json);
	const actual = untrack(() => card.actual_json);
	if (
		p.card_type === 'breath_timer' ||
		p.card_type === 'meditation_timer' ||
		p.card_type === 'strength_session'
	) {
		if (
			actual &&
			(actual.card_type === 'breath_timer' ||
				actual.card_type === 'meditation_timer' ||
				actual.card_type === 'strength_session')
		) {
			for (const [k, v] of Object.entries(actual.ratings)) {
				ratings[k] = v as number;
			}
		}
		for (const prompt of p.rating_prompts) {
			if (!(prompt.key in ratings)) ratings[prompt.key] = null;
		}
	}

	/** Emit a typed actual for timer/strength card types (fallback log mode). */
	function emitFallbackActual() {
		const pl = card.payload_json;
		const cleanRatings: Record<string, number> = {};
		for (const [k, v] of Object.entries(ratings)) {
			if (typeof v === 'number') cleanRatings[k] = v;
		}

		if (pl.card_type === 'breath_timer' || pl.card_type === 'meditation_timer') {
			onActual?.({ card_type: pl.card_type, ratings: cleanRatings, completed_cycles: null });
		} else if (pl.card_type === 'strength_session') {
			onActual?.({ card_type: 'strength_session', exercises: [], ratings: cleanRatings });
		}
		// running_workout has no rating prompts in its payload — no fallback emission needed
	}
</script>

{#if card.payload_json.card_type === 'checklist'}
	<!--
		ChecklistCard is fully implemented (Phase 2).
		payload_json is narrowed to ChecklistPayload by the type guard above.
	-->
	<ChecklistCard
		card={{ payload_json: card.payload_json, actual_json: card.actual_json }}
		{mode}
		{onActual}
	/>
{:else}
	<!-- TEMPORARY fallback — dedicated components replace this block in Phases 3-5. -->

	{#if card.payload_json.instructions}
		<p class="detail-copy">{card.payload_json.instructions}</p>
	{/if}

	{#if mode === 'log'}
		{#if card.payload_json.card_type === 'breath_timer' || card.payload_json.card_type === 'meditation_timer' || card.payload_json.card_type === 'strength_session'}
			{#if card.payload_json.rating_prompts.length > 0}
				<div class="ratings-grid">
					{#each card.payload_json.rating_prompts as prompt}
						<label class="detail-field">
							<span>{prompt.label}</span>
							<input
								type="number"
								bind:value={ratings[prompt.key]}
								min={prompt.scale_min}
								max={prompt.scale_max}
								placeholder="{prompt.scale_min}–{prompt.scale_max}"
								onchange={emitFallbackActual}
								onblur={emitFallbackActual}
							/>
						</label>
					{/each}
				</div>
			{/if}
		{/if}
	{/if}
{/if}

<style>
	.detail-copy {
		margin: 0;
		color: #a7bac6;
		font-size: 13px;
		line-height: 1.5;
	}

	/* Fallback rating inputs — mirrors today/schedule page styles */
	.ratings-grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
		gap: 8px;
	}

	.detail-field {
		display: flex;
		flex-direction: column;
		gap: 6px;
	}

	.detail-field span {
		font-family: 'DM Mono', monospace;
		font-size: 10px;
		letter-spacing: 0.14em;
		text-transform: uppercase;
		color: #8fa3b0;
	}

	input {
		border: 1px solid rgba(255, 255, 255, 0.1);
		background: rgba(8, 15, 24, 0.7);
		color: #eef5f8;
		border-radius: 8px;
		padding: 8px 10px;
		font: inherit;
		font-size: 13px;
	}
</style>
