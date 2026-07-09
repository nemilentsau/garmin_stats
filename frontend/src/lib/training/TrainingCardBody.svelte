<script lang="ts">
	/**
	 * TrainingCardBody — renders one v3 training card occurrence (`TrainingTodayCard`) for
	 * Today (mode="log") and Schedule (mode="view").
	 *
	 * Dispatches capture-bearing sections to dedicated components — TrainingStrengthGrid
	 * for `exercises_display`, TrainingCheckinGrid for `checkin_rows` — and owns the RPE
	 * number input directly (a single guarded input doesn't warrant its own component).
	 * `rule_display`, `gate_display`, `card.card.display_notes`, and `segments_display` are
	 * plain read-only text/rows in both modes; no card in the shipped v3 bundles logs
	 * segment-level actuals, so segments never get an editable form here.
	 *
	 * Capture ownership: TrainingStrengthGrid and TrainingCheckinGrid each seed themselves
	 * once (untrack, house pattern — the component is freshly mounted whenever the detail
	 * panel opens) from `card.capture` and emit the FULL TrainingCaptureLog on every change,
	 * passing through the fields they don't own from their own seed untouched. This
	 * component mirrors the same seed-once pattern for its own RPE field and additionally
	 * keeps `latestCapture` — updated by every child emission and by the RPE input — so a
	 * later RPE edit always merges against the freshest known set_logs/checkin rather than
	 * a stale snapshot. The shipped v3 bundles never combine set_rep_load[]/checkin/rpe
	 * capture on one card (see `docs/routine-pivot/block0/*.json`), so at most one of
	 * grid/checkin/rpe is ever live per card in practice; this still resolves correctly if
	 * that assumption changes.
	 */
	import { untrack } from 'svelte';
	import type { TrainingCaptureLog, TrainingTodayCard } from '$lib/api';
	import TrainingCheckinGrid from './TrainingCheckinGrid.svelte';
	import TrainingStrengthGrid from './TrainingStrengthGrid.svelte';

	let {
		card,
		mode,
		onCapture
	}: {
		card: TrainingTodayCard;
		mode: 'log' | 'view';
		onCapture?: (capture: TrainingCaptureLog) => void;
	} = $props();

	const EMPTY_CAPTURE: TrainingCaptureLog = { set_logs: [], checkin: null, rpe: null };

	// ── One-time synchronous init — never re-runs when card.capture changes. The component
	// is freshly mounted each time a detail panel opens, so reading card.capture once at
	// construction is correct and sufficient (see StrengthSessionCard for the same pattern).
	const initialCapture = untrack(() => card.capture ?? EMPTY_CAPTURE);

	/** Mirrors the latest known full capture — updated by every child emission and by the
	 *  RPE input, so whichever fires last always merges against the freshest other fields. */
	let latestCapture = $state<TrainingCaptureLog>(initialCapture);
	let rpeValue = $state<number | null>(initialCapture.rpe);

	function handleChildCapture(capture: TrainingCaptureLog) {
		latestCapture = capture;
		rpeValue = capture.rpe;
		onCapture?.(capture);
	}

	function onRpeInput(e: Event) {
		const raw = (e.currentTarget as HTMLInputElement).value;
		const num = raw === '' ? null : Number(raw);
		rpeValue = num !== null && Number.isFinite(num) ? num : null;
		const merged: TrainingCaptureLog = { ...latestCapture, rpe: rpeValue };
		latestCapture = merged;
		onCapture?.(merged);
	}
</script>

{#if card.rule_display}
	<p class="rule-line">Rule: {card.rule_display}</p>
{/if}

{#if card.gate_display}
	<p class="rule-line">{card.gate_display}</p>
{/if}

{#if card.card.display_notes}
	<p class="detail-copy">{card.card.display_notes}</p>
{/if}

{#if card.segments_display.length > 0}
	<div class="segment-list">
		{#each card.segments_display as seg}
			<div class="segment-row">
				<span class="seg-label">{seg.label}</span>
				<span class="seg-detail">{seg.detail}</span>
			</div>
		{/each}
	</div>
{/if}

{#if card.exercises_display.length > 0}
	<TrainingStrengthGrid
		card={{ exercises_display: card.exercises_display, capture: card.capture }}
		{mode}
		onCapture={handleChildCapture}
	/>
{/if}

{#if card.checkin_rows.length > 0}
	<TrainingCheckinGrid
		card={{ checkin_rows: card.checkin_rows, capture: card.capture }}
		{mode}
		onCapture={handleChildCapture}
	/>
{/if}

{#if card.capture_rpe && mode === 'log'}
	<label class="detail-field">
		<span class="field-label">RPE</span>
		<input
			type="number"
			class="num-input"
			value={rpeValue ?? ''}
			oninput={onRpeInput}
			placeholder="1–10"
			min={1}
			max={10}
			step={1}
		/>
	</label>
{/if}

<style>
	.rule-line {
		margin: 0;
		color: #6b8292;
		font-size: 11px;
		font-family: 'DM Mono', monospace;
		letter-spacing: 0.02em;
		line-height: 1.5;
	}

	.detail-copy {
		margin: 0;
		color: #a7bac6;
		font-size: 13px;
		line-height: 1.5;
	}

	.segment-list {
		display: grid;
		gap: 5px;
	}

	.segment-row {
		display: flex;
		flex-direction: column;
		gap: 3px;
		padding: 8px 10px;
		border-radius: 7px;
		background: rgba(255, 255, 255, 0.03);
	}

	.seg-label {
		color: #c5d8e4;
		font-size: 13px;
		font-weight: 500;
	}

	.seg-detail {
		color: #6b8292;
		font-family: 'DM Mono', monospace;
		font-size: 11px;
		letter-spacing: 0.02em;
		font-variant-numeric: tabular-nums;
	}

	.detail-field {
		display: flex;
		flex-direction: column;
		gap: 5px;
		max-width: 140px;
	}

	.field-label {
		font-family: 'DM Mono', monospace;
		font-size: 10px;
		letter-spacing: 0.14em;
		text-transform: uppercase;
		color: #8fa3b0;
	}

	.num-input {
		border: 1px solid rgba(255, 255, 255, 0.1);
		background: rgba(8, 15, 24, 0.7);
		color: #eef5f8;
		border-radius: 8px;
		padding: 7px 10px;
		font: inherit;
		font-size: 13px;
		font-family: 'DM Mono', monospace;
		font-variant-numeric: tabular-nums;
		width: 100%;
		box-sizing: border-box;
		appearance: textfield;
		-moz-appearance: textfield;
	}

	.num-input::-webkit-outer-spin-button,
	.num-input::-webkit-inner-spin-button {
		-webkit-appearance: none;
		margin: 0;
	}

	.num-input:focus {
		outline: none;
		border-color: rgba(74, 144, 217, 0.4);
	}
</style>
