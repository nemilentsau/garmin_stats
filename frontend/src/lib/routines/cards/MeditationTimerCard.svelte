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
	import type { ScheduleOccurrence, TodayCard } from '$lib/api';

	type MeditationPayload = Extract<
		ScheduleOccurrence['payload_json'],
		{ card_type: 'meditation_timer' }
	>;
	type FullActual = TodayCard['actual_json'];
	export type TimerActual = {
		card_type: 'meditation_timer';
		ratings: Record<string, number>;
		completed_cycles: null;
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

	const existingActual = $derived(
		card.actual_json?.card_type === 'meditation_timer' ? card.actual_json : null
	);

	// ── Ratings state ─────────────────────────────────────────────────────────
	let ratings = $state<Record<string, number | null>>({});

	// Seed from persisted actual whenever the card identity changes.
	$effect(() => {
		for (const p of prompts) {
			ratings[p.key] = existingActual?.ratings?.[p.key] ?? null;
		}
	});

	function emit() {
		const clean: Record<string, number> = {};
		for (const [k, v] of Object.entries(ratings)) {
			if (typeof v === 'number') clean[k] = v;
		}
		onActual?.({
			card_type: 'meditation_timer',
			ratings: clean,
			completed_cycles: null
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

	/* Ratings */
	.ratings-section {
		margin-top: 4px;
	}

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
