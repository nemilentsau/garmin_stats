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
	 * `docs/routine-pivot/block1/*.json`) from silently reverting a sibling's staged edit.
	 *
	 * Run-link (`associated_activity`/`run_candidates`, `running.v3` cards only — every other
	 * card gets both empty/null from the backend, so the block below is naturally a no-op for
	 * them) is a separate concern from `TrainingCaptureLog`: it has its own backend fields
	 * (`linked_run_id`/`run_link_detached`) and its own PATCH, so it does NOT flow through
	 * `latestCapture`/`onCapture`. This component only displays `associated_activity` and the
	 * `run_candidates` picker and emits the user's choice via `onRunLink`; it does no matching
	 * itself (display-only rule) — the page owns the PATCH call and refetches the Today feed
	 * on success, since a run-link change can change what every other run card that day
	 * displays too (multiple run cards share the same day's `run_candidates`).
	 */
	import { untrack } from 'svelte';
	import type { TrainingCaptureLog, TrainingTodayCard } from '$lib/api';
	import { fmtDuration, fmtLoad, fmtMi, fmtPace, fmtStartTime, fmtTE, hrBadgeLabel } from '$lib/format-run';
	import TrainingCheckinGrid from './TrainingCheckinGrid.svelte';
	import TrainingStrengthGrid from './TrainingStrengthGrid.svelte';

	/** Partial run-link PATCH — mirrors `TrainingLogUpdateRequest`'s `linked_run_id`/
	 *  `run_link_detached` fields; the page owns the actual PATCH + feed refresh. */
	type RunLinkPatch = { linked_run_id?: string | null; run_link_detached?: boolean | null };

	let {
		card,
		mode,
		onCapture,
		onRunLink
	}: {
		card: TrainingTodayCard;
		mode: 'log' | 'view';
		onCapture?: (capture: TrainingCaptureLog) => void;
		onRunLink?: (patch: RunLinkPatch) => void;
	} = $props();

	const EMPTY_CAPTURE: TrainingCaptureLog = { set_logs: [], checkin: null, rpe: null };
	const MEASUREMENT_LABELS = {
		awaiting_review: 'Awaiting review',
		valid: 'Valid',
		provisional: 'Provisional',
		failed: 'Failed'
	} as const;
	const GATE_RESULT_LABELS = {
		pass: 'Pass',
		fail: 'Fail',
		unknown: 'Unknown'
	} as const;
	const SIGNAL_LABELS: Record<string, string> = {
		'env.dew_point': 'Dew point',
		'strap.validity_pct': 'Strap validity'
	};

	// ── One-time synchronous init — never re-runs when card.capture changes. The component
	// is freshly mounted each time a detail panel opens, so reading card.capture once at
	// construction is correct and sufficient (see StrengthSessionCard for the same pattern).
	const initialCapture = untrack(() => card.capture ?? EMPTY_CAPTURE);

	/** The single composed capture — updated field-by-field by each child's own-slice
	 *  callback and by the RPE input, then re-emitted in full via onCapture. */
	let latestCapture = $state<TrainingCaptureLog>(initialCapture);
	let rpeValue = $state<number | null>(initialCapture.rpe);

	/** Run-candidate picker visibility — opened by "Not this run?" (already linked) or
	 *  "Link a run…" (unlinked with candidates); closed on pick, detach, or toggle. */
	let runPickerOpen = $state(false);

	function pickRun(runId: string) {
		runPickerOpen = false;
		onRunLink?.({ linked_run_id: runId });
	}

	/** Clears both the manual link and sets `run_link_detached`. A stored `linked_run_id`
	 *  always wins over `run_link_detached` alone (backend `match_run_to_card` precedence),
	 *  so Detach must send both fields — otherwise detaching a manually-linked card would
	 *  be a no-op, since the stale `linked_run_id` would keep resolving the association. */
	function detachRun() {
		runPickerOpen = false;
		onRunLink?.({ linked_run_id: null, run_link_detached: true });
	}

	function fmtBpm(value: number | null): string {
		return value == null ? '—' : `${Math.round(value)} bpm`;
	}

	function fmtValidity(value: number | null): string {
		return value == null ? '—' : `${(value * 100).toFixed(1)}%`;
	}

	function signalLabel(signal: string): string {
		return SIGNAL_LABELS[signal] ?? signal;
	}

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

{#if card.associated_activity || (mode === 'log' && card.run_candidates.length > 0)}
	<div class="executed-block">
		{#if card.associated_activity}
			{@const activity = card.associated_activity}
			<div class="executed-header">
				<span class="executed-title">Executed</span>
				<span class="link-badge" class:auto={activity.link_source === 'auto'}>
					{activity.link_source === 'auto' ? 'auto-linked' : 'linked'}
				</span>
			</div>
			<div class="executed-stats">
				<span class="executed-stat"><span class="executed-primary">{fmtMi(activity.distance_mi)}</span></span>
				<span class="executed-stat">{fmtDuration(activity.timer_time_s)}</span>
				<span class="executed-stat">{fmtPace(activity.pace_min_per_mi)}</span>
				{#if activity.avg_heart_rate_bpm != null}
					<span class="executed-stat">
						{Math.round(activity.avg_heart_rate_bpm)} bpm
						{#if hrBadgeLabel(activity.hr_source)}
							<span class="hr-badge" class:chest={hrBadgeLabel(activity.hr_source) === 'CHEST'}
								>{hrBadgeLabel(activity.hr_source)}</span
							>
						{/if}
					</span>
				{/if}
				{#if activity.training_load != null}
					<span class="executed-stat">{fmtLoad(activity.training_load)} load</span>
				{/if}
				{#if activity.aerobic_training_effect != null}
					<span class="executed-stat">TE {fmtTE(activity.aerobic_training_effect)}</span>
				{/if}
				<span class="executed-stat executed-muted">{fmtStartTime(activity.start_time_local)}</span>
			</div>
			<div class="executed-actions">
				<a class="view-run-link" href={`/runs/${activity.run_id}`}>View run →</a>
				{#if mode === 'log'}
					<button type="button" class="link-action" onclick={() => (runPickerOpen = !runPickerOpen)}>
						Not this run?
					</button>
					<button type="button" class="link-action" onclick={detachRun}>Detach</button>
				{/if}
			</div>
		{:else if mode === 'log' && card.run_candidates.length > 0}
			<button type="button" class="link-affordance" onclick={() => (runPickerOpen = !runPickerOpen)}>
				Link a run…
			</button>
		{/if}

		{#if runPickerOpen && mode === 'log'}
			<div class="run-picker" role="radiogroup" aria-label="Select the tracked run for this session">
				{#each card.run_candidates as candidate (candidate.run_id)}
					<label class="run-picker-row">
						<input
							type="radio"
							name={`run-candidate-${card.occurrence_key}`}
							checked={card.associated_activity?.run_id === candidate.run_id}
							onchange={() => pickRun(candidate.run_id)}
						/>
						<span class="run-picker-time">{fmtStartTime(candidate.start_time_local)}</span>
						<span class="run-picker-dist">{fmtMi(candidate.distance_mi)}</span>
					</label>
				{/each}
			</div>
		{/if}
	</div>
{/if}

{#if card.measurement}
	{@const measurement = card.measurement}
	{@const measurementHeadingId = `measurement-heading-${card.occurrence_key}`}
	{@const observations = measurement.observations}
	<section
		class="measurement-evidence"
		data-status={measurement.status}
		aria-labelledby={measurementHeadingId}
	>
		<div id={measurementHeadingId} class="measurement-heading">
			<span>Measurement</span>
			<strong>{MEASUREMENT_LABELS[measurement.status]}</strong>
		</div>
		{#if measurement.rationale}
			<p class="measurement-rationale">{measurement.rationale}</p>
		{/if}
		<dl class="measurement-observations">
			<div>
				<dt>LTHR observation</dt>
				<dd>{fmtBpm(observations.final20_hr_bpm)}</dd>
			</div>
			<div>
				<dt>Threshold pace</dt>
				<dd>{fmtPace(observations.threshold_pace_min_per_mi)}</dd>
			</div>
			<div>
				<dt>Strap validity</dt>
				<dd>{fmtValidity(observations.strap_validity_pct)}</dd>
			</div>
		</dl>
		{#if !measurement.estimator_eligible || measurement.retry_required}
			<div class="measurement-limits">
				{#if !measurement.estimator_eligible}
					<p>Not used to update zones.</p>
				{/if}
				{#if measurement.retry_required}
					<p>Another measurement attempt is required.</p>
				{/if}
			</div>
		{/if}
		{#if measurement.gates.length > 0}
			<ul class="measurement-rows" aria-label="Measurement quality gates">
				{#each measurement.gates as gate, gateIndex (gate.signal + ':' + gate.operator + ':' + String(gate.threshold) + ':' + gateIndex)}
					<li class="measurement-row">
						<span>{signalLabel(gate.signal)}</span>
						<strong>{GATE_RESULT_LABELS[gate.result]}</strong>
					</li>
				{/each}
			</ul>
		{/if}
		{#if measurement.warnings.length > 0}
			<ul class="measurement-warnings" aria-label="Measurement observations">
				{#each measurement.warnings as warning, warningIndex (warning.code + ':' + warningIndex)}
					<li>{warning.message}</li>
				{/each}
			</ul>
		{/if}
	</section>
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

	/* ── Executed block (run-link) — a quiet sub-block adjacent to segment-list, not a
	   card-in-card: same background tint as segment-list rows, no border/shadow of its own. */
	.executed-block {
		display: flex;
		flex-direction: column;
		gap: 8px;
		padding: 8px 10px;
		border-radius: 7px;
		background: rgba(255, 255, 255, 0.025);
	}

	.executed-header {
		display: flex;
		align-items: center;
		gap: 8px;
	}

	.executed-title {
		font-family: 'DM Mono', monospace;
		font-size: 10px;
		letter-spacing: 0.14em;
		text-transform: uppercase;
		color: #8fa3b0;
	}

	.link-badge {
		display: inline-block;
		padding: 1px 6px;
		border-radius: 3px;
		font-size: 9px;
		font-weight: 500;
		letter-spacing: 0.05em;
		color: #8fa3b0;
		background: rgba(255, 255, 255, 0.06);
	}

	.link-badge.auto {
		color: #5bb5a6;
		background: rgba(91, 181, 166, 0.12);
	}

	.executed-stats {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 3px 12px;
		font-family: 'DM Mono', monospace;
		font-size: 12px;
		font-variant-numeric: tabular-nums;
		color: #c5d8e4;
	}

	.executed-primary {
		color: #eef5f8;
		font-weight: 600;
	}

	.executed-muted {
		color: #6b8292;
	}

	.hr-badge {
		display: inline-block;
		margin-left: 4px;
		padding: 1px 5px;
		border-radius: 3px;
		font-size: 9px;
		font-weight: 500;
		letter-spacing: 0.05em;
		color: #8fa3b0;
		background: rgba(255, 255, 255, 0.06);
		vertical-align: middle;
	}

	.hr-badge.chest {
		color: #5bb5a6;
		background: rgba(91, 181, 166, 0.12);
	}

	.executed-actions {
		display: flex;
		align-items: center;
		gap: 12px;
	}

	.view-run-link {
		color: #7bb8e0;
		font-family: 'DM Mono', monospace;
		font-size: 11px;
		text-decoration: none;
	}

	.view-run-link:hover {
		text-decoration: underline;
	}

	.link-action {
		border: none;
		background: transparent;
		color: #8fa3b0;
		font-family: 'DM Mono', monospace;
		font-size: 11px;
		letter-spacing: 0.02em;
		cursor: pointer;
		padding: 0;
	}

	.link-action:hover {
		color: #c3d3dd;
		text-decoration: underline;
	}

	.link-affordance {
		align-self: flex-start;
		border: 1px dashed rgba(255, 255, 255, 0.14);
		background: transparent;
		color: #8fa3b0;
		font-family: 'DM Mono', monospace;
		font-size: 11px;
		letter-spacing: 0.02em;
		border-radius: 6px;
		padding: 5px 10px;
		cursor: pointer;
	}

	.link-affordance:hover {
		color: #c3d3dd;
		border-color: rgba(255, 255, 255, 0.28);
	}

	.run-picker {
		display: flex;
		flex-direction: column;
		gap: 2px;
		border-top: 1px solid rgba(255, 255, 255, 0.06);
		padding-top: 8px;
	}

	.run-picker-row {
		display: flex;
		align-items: center;
		gap: 8px;
		padding: 5px 4px;
		border-radius: 5px;
		cursor: pointer;
		font-family: 'DM Mono', monospace;
		font-size: 12px;
		font-variant-numeric: tabular-nums;
		color: #c5d8e4;
	}

	.run-picker-row:hover {
		background: rgba(255, 255, 255, 0.04);
	}

	.run-picker-row input[type='radio'] {
		accent-color: #5bb5a6;
	}

	.run-picker-dist {
		color: #6b8292;
	}

	/* One aligned evidence section for facets of the same measurement result. It stays
	   visually subordinate to Executed and deliberately has no nested-card chrome. */
	.measurement-evidence {
		display: flex;
		flex-direction: column;
		align-self: flex-start;
		gap: 7px;
		box-sizing: border-box;
		width: min(100%, 600px);
		padding-left: 10px;
		border-left: 2px solid rgba(143, 163, 176, 0.5);
		font-size: 12px;
		color: #a7bac6;
	}

	.measurement-evidence[data-status='valid'] {
		border-left-color: #5bb5a6;
	}

	.measurement-evidence[data-status='provisional'] {
		border-left-color: #d4944c;
	}

	.measurement-evidence[data-status='failed'] {
		border-left-color: #e85d4a;
	}

	.measurement-heading {
		display: flex;
		align-items: baseline;
		gap: 8px;
		margin: 0;
		font-family: 'DM Mono', monospace;
		font-size: 10px;
		letter-spacing: 0.12em;
		text-transform: uppercase;
		color: #8fa3b0;
	}

	.measurement-heading strong {
		color: #8fa3b0;
		font-size: 10px;
		font-weight: 600;
		letter-spacing: 0.06em;
	}

	.measurement-evidence[data-status='valid'] .measurement-heading strong {
		color: #5bb5a6;
	}

	.measurement-evidence[data-status='provisional'] .measurement-heading strong {
		color: #d4944c;
	}

	.measurement-evidence[data-status='failed'] .measurement-heading strong {
		color: #e85d4a;
	}

	.measurement-rationale,
	.measurement-limits p {
		margin: 0;
		line-height: 1.45;
	}

	.measurement-rationale {
		color: #c5d8e4;
	}

	.measurement-observations {
		display: grid;
		gap: 3px;
		margin: 0;
		font-family: 'DM Mono', monospace;
		font-variant-numeric: tabular-nums lining-nums;
	}

	.measurement-observations > div,
	.measurement-row {
		display: grid;
		grid-template-columns: minmax(140px, 1fr) minmax(84px, auto);
		align-items: baseline;
		gap: 16px;
	}

	.measurement-observations dt {
		color: #8fa3b0;
	}

	.measurement-observations dd {
		margin: 0;
		color: #d7e3e9;
		text-align: right;
	}

	.measurement-limits {
		display: flex;
		gap: 4px 14px;
		flex-wrap: wrap;
		color: #8fa3b0;
		font-size: 11px;
	}

	.measurement-rows {
		display: grid;
		gap: 3px;
		margin: 0;
		list-style: none;
		padding-left: 0;
		padding-top: 5px;
		border-top: 1px solid rgba(255, 255, 255, 0.06);
		font-family: 'DM Mono', monospace;
		font-variant-numeric: tabular-nums lining-nums;
	}

	.measurement-row span {
		color: #8fa3b0;
	}

	.measurement-row strong {
		color: #c5d8e4;
		font-weight: 500;
		text-align: right;
	}

	.measurement-warnings {
		display: grid;
		gap: 3px;
		margin: 0;
		padding: 0;
		list-style: none;
		color: #a7bac6;
		font-size: 11px;
		line-height: 1.45;
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
