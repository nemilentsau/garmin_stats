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
	 * Capture ownership: children own their slice; CardBody composes. TrainingStrengthGrid
	 * emits ONLY `set_logs` (via `onSetLogs`) and TrainingCheckinGrid emits ONLY `checkin`
	 * (via `onCheckin`) — neither reads nor replays a sibling's capture kind. This component
	 * is the single owner of the composed `TrainingCaptureLog`: it seeds `latestCapture` once
	 * (untrack, house pattern — the component is freshly mounted whenever the detail panel
	 * opens) from `card.capture`, then updates just the relevant field on each child callback
	 * or on its own RPE input and re-emits the full merged log via `onCapture`. Centralizing
	 * the merge here — rather than having each child replay the other slices from its own
	 * stale seed — is what prevents a card that combines capture kinds (nothing in the schema
	 * forbids it, even though the shipped v3 bundles don't do so today, see
	 * `docs/routine-pivot/block0/*.json`) from silently reverting a sibling's staged edit.
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

	/** The single composed capture — updated field-by-field by each child's own-slice
	 *  callback and by the RPE input, then re-emitted in full via onCapture. */
	let latestCapture = $state<TrainingCaptureLog>(initialCapture);
	let rpeValue = $state<number | null>(initialCapture.rpe);

	// Human-readable badge for the card's selection rule: the effective variant in plain
	// words, with the raw HRV/soreness rule kept in the tooltip.
	const variantMeta = $derived.by((): { label: string; tone: 'ok' | 'warn' } => {
		switch (card.variant_taken) {
			case 'skip':
				return { label: 'Skipped', tone: 'warn' };
			case 'reduced':
				return { label: 'Reduced', tone: 'warn' };
			case 'plus':
				return { label: 'Plus', tone: 'ok' };
			default:
				return { label: 'Full', tone: 'ok' };
		}
	});

	function handleSetLogs(setLogs: TrainingCaptureLog['set_logs']) {
		latestCapture = { ...latestCapture, set_logs: setLogs };
		onCapture?.(latestCapture);
	}

	function handleCheckin(checkin: TrainingCaptureLog['checkin']) {
		latestCapture = { ...latestCapture, checkin };
		onCapture?.(latestCapture);
	}

	function onRpeInput(e: Event) {
		const raw = (e.currentTarget as HTMLInputElement).value;
		const num = raw === '' ? null : Number(raw);
		rpeValue = num !== null && Number.isFinite(num) ? num : null;
		latestCapture = { ...latestCapture, rpe: rpeValue };
		onCapture?.(latestCapture);
	}
</script>

{#if card.rule_display}
	<span class="rule-badge {variantMeta.tone}" title={`Rule — ${card.rule_display}`}>{variantMeta.label}</span>
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
				{#if seg.distance_mi != null || seg.duration_min != null || seg.zone}
					<span class="seg-detail">
						{#if seg.distance_mi != null}<span class="seg-primary">{seg.distance_mi} mi</span>{/if}
						{#if seg.duration_min != null}<span class="seg-sub">{seg.duration_min} min</span>{/if}
						{#if seg.zone}<span class="seg-sub">{seg.zone}</span>{/if}
					</span>
				{:else}
					<span class="seg-detail">{seg.detail}</span>
				{/if}
			</div>
		{/each}
	</div>
{/if}

{#if card.exercises_display.length > 0}
	<TrainingStrengthGrid
		card={{ exercises_display: card.exercises_display, capture: card.capture }}
		{mode}
		onSetLogs={handleSetLogs}
	/>
{/if}

{#if card.checkin_rows.length > 0}
	<TrainingCheckinGrid
		card={{ checkin_rows: card.checkin_rows, capture: card.capture }}
		{mode}
		onCheckin={handleCheckin}
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

	.rule-badge {
		align-self: flex-start;
		display: inline-block;
		font-size: 12px;
		border-radius: 6px;
		padding: 3px 9px;
		cursor: default;
	}
	.rule-badge.ok {
		color: #86efac;
		background: rgba(34, 90, 54, 0.28);
		border: 1px solid rgba(46, 110, 66, 0.5);
	}
	.rule-badge.warn {
		color: #f4c67a;
		background: rgba(120, 82, 20, 0.28);
		border: 1px solid rgba(150, 110, 40, 0.5);
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

	.seg-primary {
		color: #eef5f8;
		font-weight: 600;
	}

	.seg-sub {
		margin-left: 8px;
		color: #6b8292;
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
