<script lang="ts">
	/**
	 * RunningWorkoutCard — dedicated card for running_workout payloads.
	 *
	 * view mode: humanized workout_type header, chips for RPE/talk_test/hr_guidance,
	 * calibration-quality badge, and a segment list showing label, kind, prescription,
	 * and optional detail — read-only summary for Schedule.
	 *
	 * log mode: actuals form (distance_km, duration_min, avg_hr, hr_drift_pct, rpe,
	 * calibration_quality toggle) plus a confounder section rendering each
	 * post_run_fields entry as a labeled input. Emits RunningActual on every change.
	 * Prefills from existing card.actual_json when the card_type matches. Free-text
	 * notes are deliberately NOT part of the actual — the Today detail panel owns the
	 * single card-level notes field (CardLog.notes).
	 *
	 * All numeric inputs use one-way value + guarded oninput handlers (no deep bind:value)
	 * to avoid Svelte 5 deep-bind setter throws. State is seeded synchronously via untrack.
	 * No statistical computation happens here — pace, pace-zones, etc. are backend concerns.
	 */
	import { untrack } from 'svelte';
	import type { ScheduleOccurrence, TodayCard } from '$lib/api';

	type RunningPayload = Extract<
		ScheduleOccurrence['payload_json'],
		{ card_type: 'running_workout' }
	>;
	type FullActual = TodayCard['actual_json'];

	export type RunningActual = {
		card_type: 'running_workout';
		distance_km: number | null;
		duration_min: number | null;
		avg_hr: number | null;
		hr_drift_pct: number | null;
		calibration_quality: boolean;
		rpe: number | null;
		post_run: Record<string, number | string | null>;
	};

	let {
		card,
		mode,
		onActual
	}: {
		card: { payload_json: RunningPayload; actual_json?: FullActual };
		mode: 'log' | 'view';
		onActual?: (actual: RunningActual) => void;
	} = $props();

	const payload = $derived(card.payload_json);

	// ── One-time synchronous init — never re-runs when actual_json changes ────
	// The component is freshly mounted each time a detail panel opens ({#if isExpanded}),
	// so reading card.actual_json once at construction is correct and sufficient.
	// Using untrack prevents the surrounding reactive context from tracking actual_json.
	const initialActual = untrack(() =>
		card.actual_json?.card_type === 'running_workout' ? card.actual_json : null
	);
	const initialFields = untrack(() => card.payload_json.post_run_fields ?? []);

	// ── Mutable log state ─────────────────────────────────────────────────────
	let distanceKm = $state<number | null>(initialActual?.distance_km ?? null);
	let durationMin = $state<number | null>(initialActual?.duration_min ?? null);
	let avgHr = $state<number | null>(initialActual?.avg_hr ?? null);
	let hrDriftPct = $state<number | null>(initialActual?.hr_drift_pct ?? null);
	let rpeVal = $state<number | null>(initialActual?.rpe ?? null);
	let calibrationQuality = $state<boolean>(initialActual?.calibration_quality ?? false);

	// Post-run confounder fields keyed by field.key
	let postRun = $state<Record<string, number | string | null>>(
		buildInitialPostRun(initialFields, initialActual?.post_run ?? {})
	);

	// ── Helpers ───────────────────────────────────────────────────────────────

	/** Build initial post_run record from field definitions + any existing values. */
	function buildInitialPostRun(
		fields: RunningPayload['post_run_fields'],
		existing: Record<string, number | string | null>
	): Record<string, number | string | null> {
		const result: Record<string, number | string | null> = {};
		for (const f of fields) {
			result[f.key] = existing[f.key] ?? null;
		}
		return result;
	}

	/** Build a clean RunningActual from current state. */
	function buildActual(): RunningActual {
		return {
			card_type: 'running_workout',
			distance_km: distanceKm,
			duration_min: durationMin,
			avg_hr: avgHr,
			hr_drift_pct: hrDriftPct,
			calibration_quality: calibrationQuality,
			rpe: rpeVal,
			post_run: { ...postRun }
		};
	}

	/** Coerce raw input string → number|null (empty or NaN → null). */
	function coerceNum(raw: string): number | null {
		if (raw === '') return null;
		const n = Number(raw);
		return Number.isFinite(n) ? n : null;
	}

	/** Coerce raw input string → integer|null; avg_hr and rpe are int-typed in the contract. */
	function coerceIntNum(raw: string): number | null {
		const n = coerceNum(raw);
		return n === null ? null : Math.round(n);
	}

	// Guarded numeric input handlers — write to tracked $state, then emit.
	// Using explicit setters avoids Svelte 5 deep-bind setter throws.
	function onDistanceInput(e: Event) {
		distanceKm = coerceNum((e.currentTarget as HTMLInputElement).value);
		emit();
	}
	function onDurationInput(e: Event) {
		durationMin = coerceNum((e.currentTarget as HTMLInputElement).value);
		emit();
	}
	function onAvgHrInput(e: Event) {
		avgHr = coerceIntNum((e.currentTarget as HTMLInputElement).value);
		emit();
	}
	function onHrDriftInput(e: Event) {
		hrDriftPct = coerceNum((e.currentTarget as HTMLInputElement).value);
		emit();
	}
	function onRpeInput(e: Event) {
		rpeVal = coerceIntNum((e.currentTarget as HTMLInputElement).value);
		emit();
	}
	function onCalibrationChange(e: Event) {
		calibrationQuality = (e.currentTarget as HTMLInputElement).checked;
		emit();
	}

	/** Handler for a confounder field input change. */
	function onPostRunInput(key: string, fieldType: 'number' | 'text', e: Event) {
		const raw = (e.currentTarget as HTMLInputElement).value;
		if (fieldType === 'number') {
			postRun[key] = coerceNum(raw);
		} else {
			postRun[key] = raw || null;
		}
		emit();
	}

	function emit() {
		onActual?.(buildActual());
	}

	// ── Display helpers ────────────────────────────────────────────────────────

	/** Humanize a snake_case workout_type string for display. */
	function humanize(s: string): string {
		return s.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
	}

	const KIND_LABELS: Record<string, string> = {
		warmup: 'Warm-up',
		main: 'Main',
		strides: 'Strides',
		cooldown: 'Cool-down',
		intervals: 'Intervals'
	};
</script>

{#if payload.instructions}
	<p class="detail-copy">{payload.instructions}</p>
{/if}

<!-- ── META HEADER (shared between view + log) ─────────────────────────────── -->
<div class="meta-row">
	<span class="workout-type">{humanize(payload.workout_type)}</span>
	{#if payload.rpe}
		<span class="chip chip-rpe">RPE {payload.rpe}</span>
	{/if}
	{#if payload.talk_test}
		<span class="chip chip-talk">{payload.talk_test}</span>
	{/if}
	{#if payload.hr_guidance}
		<span class="chip chip-hr">{payload.hr_guidance}</span>
	{/if}
	{#if payload.calibration_quality}
		<span class="chip chip-strap">chest-strap</span>
	{/if}
</div>

{#if mode === 'view'}
	<!-- ── VIEW MODE ─────────────────────────────────────────────────────────── -->
	{#if payload.segments.length > 0}
		<div class="segment-list">
			{#each payload.segments as seg}
				<div class="segment-row">
					<div class="seg-header">
						<span class="seg-label">{seg.label}</span>
						<span class="seg-kind">{KIND_LABELS[seg.kind] ?? seg.kind}</span>
					</div>
					<span class="seg-prescription">{seg.prescription}</span>
					{#if seg.detail}
						<span class="seg-detail">{seg.detail}</span>
					{/if}
				</div>
			{/each}
		</div>
	{/if}
{:else}
	<!-- ── LOG MODE ──────────────────────────────────────────────────────────── -->

	<!-- Actuals grid -->
	<div class="actuals-section">
		<div class="actuals-grid">
			<!-- Distance -->
			<label class="detail-field">
				<span class="field-label">Distance</span>
				<div class="input-with-unit">
					<input
						type="number"
						class="num-input"
						value={distanceKm ?? ''}
						oninput={onDistanceInput}
						placeholder="—"
						min={0}
						step={0.1}
					/>
					<span class="unit-hint">km</span>
				</div>
			</label>

			<!-- Duration -->
			<label class="detail-field">
				<span class="field-label">Duration</span>
				<div class="input-with-unit">
					<input
						type="number"
						class="num-input"
						value={durationMin ?? ''}
						oninput={onDurationInput}
						placeholder="—"
						min={0}
						step={1}
					/>
					<span class="unit-hint">min</span>
				</div>
			</label>

			<!-- Avg HR -->
			<label class="detail-field">
				<span class="field-label">Avg HR</span>
				<div class="input-with-unit">
					<input
						type="number"
						class="num-input"
						value={avgHr ?? ''}
						oninput={onAvgHrInput}
						placeholder="—"
						min={0}
						max={240}
						step={1}
					/>
					<span class="unit-hint">bpm</span>
				</div>
			</label>

			<!-- HR Drift -->
			<label class="detail-field">
				<span class="field-label">HR Drift</span>
				<div class="input-with-unit">
					<input
						type="number"
						class="num-input"
						value={hrDriftPct ?? ''}
						oninput={onHrDriftInput}
						placeholder="—"
						min={0}
						max={100}
						step={0.1}
					/>
					<span class="unit-hint">%</span>
				</div>
			</label>

			<!-- RPE -->
			<label class="detail-field">
				<span class="field-label">RPE</span>
				<input
					type="number"
					class="num-input"
					value={rpeVal ?? ''}
					oninput={onRpeInput}
					placeholder="1–10"
					min={1}
					max={10}
					step={1}
				/>
			</label>

			<!-- Calibration quality toggle -->
			<div class="detail-field calibration-field">
				<span class="field-label">Chest Strap</span>
				<label class="toggle-label">
					<input
						type="checkbox"
						class="toggle-input"
						checked={calibrationQuality}
						onchange={onCalibrationChange}
					/>
					<span class="toggle-track" class:checked={calibrationQuality}>
						<span class="toggle-thumb"></span>
					</span>
					<span class="toggle-text">{calibrationQuality ? 'Used' : 'Not used'}</span>
				</label>
			</div>
		</div>
	</div>

	<!-- Confounder fields (post_run_fields) -->
	{#if payload.post_run_fields.length > 0}
		<div class="confounders-section">
			<span class="section-label">Post-run</span>
			<div class="confounders-grid">
				{#each payload.post_run_fields as field}
					<label class="detail-field">
						<span class="field-label">{field.label}</span>
						{#if field.field_type === 'number'}
							<div class="input-with-unit">
								<input
									type="number"
									class="num-input"
									value={postRun[field.key] ?? ''}
									oninput={(e) => onPostRunInput(field.key, 'number', e)}
									onchange={(e) => onPostRunInput(field.key, 'number', e)}
									placeholder="—"
									step={field.unit === '%' ? 0.1 : 1}
								/>
								{#if field.unit}
									<span class="unit-hint">{field.unit}</span>
								{/if}
							</div>
						{:else}
							<input
								type="text"
								class="text-input"
								value={(postRun[field.key] as string) ?? ''}
								oninput={(e) => onPostRunInput(field.key, 'text', e)}
								onchange={(e) => onPostRunInput(field.key, 'text', e)}
								placeholder="—"
							/>
						{/if}
					</label>
				{/each}
			</div>
		</div>
	{/if}

	<!-- Segment list (reference, collapsed into view) -->
	{#if payload.segments.length > 0}
		<div class="segment-list log-segments">
			{#each payload.segments as seg}
				<div class="segment-row">
					<div class="seg-header">
						<span class="seg-label">{seg.label}</span>
						<span class="seg-kind">{KIND_LABELS[seg.kind] ?? seg.kind}</span>
					</div>
					<span class="seg-prescription">{seg.prescription}</span>
					{#if seg.detail}
						<span class="seg-detail">{seg.detail}</span>
					{/if}
				</div>
			{/each}
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

	/* ── Meta row ──────────────────────────────────────────────────────────── */
	.meta-row {
		display: flex;
		align-items: center;
		gap: 8px;
		flex-wrap: wrap;
	}

	.workout-type {
		color: #c5d8e4;
		font-size: 13px;
		font-weight: 500;
		letter-spacing: 0.01em;
	}

	/* Chips */
	.chip {
		display: inline-block;
		padding: 2px 7px;
		border-radius: 5px;
		font-family: 'DM Mono', monospace;
		font-size: 11px;
		letter-spacing: 0.05em;
	}

	.chip-rpe {
		background: rgba(74, 144, 217, 0.12);
		border: 1px solid rgba(74, 144, 217, 0.25);
		color: #4a90d9;
	}

	.chip-talk {
		background: rgba(72, 187, 120, 0.1);
		border: 1px solid rgba(72, 187, 120, 0.25);
		color: #48bb78;
	}

	.chip-hr {
		background: rgba(237, 137, 54, 0.1);
		border: 1px solid rgba(237, 137, 54, 0.25);
		color: #ed8936;
	}

	.chip-strap {
		background: rgba(214, 158, 46, 0.1);
		border: 1px solid rgba(214, 158, 46, 0.25);
		color: #d6a030;
		letter-spacing: 0.08em;
	}

	/* ── Segment list ──────────────────────────────────────────────────────── */
	.segment-list {
		display: grid;
		gap: 5px;
	}

	.log-segments {
		margin-top: 2px;
		opacity: 0.7;
	}

	.segment-row {
		display: flex;
		flex-direction: column;
		gap: 3px;
		padding: 8px 10px;
		border-radius: 7px;
		background: rgba(255, 255, 255, 0.03);
	}

	.seg-header {
		display: flex;
		align-items: center;
		gap: 8px;
		flex-wrap: wrap;
	}

	.seg-label {
		color: #c5d8e4;
		font-size: 13px;
		font-weight: 500;
	}

	.seg-kind {
		font-family: 'DM Mono', monospace;
		font-size: 10px;
		color: #6b8292;
		background: rgba(255, 255, 255, 0.05);
		border: 1px solid rgba(255, 255, 255, 0.08);
		border-radius: 4px;
		padding: 2px 5px;
		letter-spacing: 0.06em;
	}

	.seg-prescription {
		color: #eef5f8;
		font-family: 'DM Mono', monospace;
		font-size: 12px;
		letter-spacing: 0.04em;
		font-variant-numeric: tabular-nums;
	}

	.seg-detail {
		color: #6b8292;
		font-size: 11px;
		line-height: 1.4;
	}

	/* ── Actuals section ───────────────────────────────────────────────────── */
	.actuals-section {
		display: grid;
		gap: 10px;
	}

	.actuals-grid {
		display: grid;
		grid-template-columns: repeat(2, 1fr);
		gap: 8px;
	}

	.detail-field {
		display: flex;
		flex-direction: column;
		gap: 5px;
	}

	.field-label {
		font-family: 'DM Mono', monospace;
		font-size: 10px;
		letter-spacing: 0.14em;
		text-transform: uppercase;
		color: #8fa3b0;
	}

	/* Number input with optional unit suffix */
	.input-with-unit {
		display: flex;
		align-items: center;
		gap: 0;
		border: 1px solid rgba(255, 255, 255, 0.1);
		border-radius: 8px;
		background: rgba(8, 15, 24, 0.7);
		overflow: hidden;
	}

	.input-with-unit .num-input {
		border: none;
		border-radius: 0;
		background: transparent;
		flex: 1;
		min-width: 0;
	}

	.unit-hint {
		padding: 0 8px 0 4px;
		font-family: 'DM Mono', monospace;
		font-size: 11px;
		color: #4a5568;
		white-space: nowrap;
		flex-shrink: 0;
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

	.input-with-unit .num-input:focus {
		outline: none;
	}

	.input-with-unit:focus-within {
		border-color: rgba(74, 144, 217, 0.4);
	}

	.text-input {
		border: 1px solid rgba(255, 255, 255, 0.1);
		background: rgba(8, 15, 24, 0.7);
		color: #eef5f8;
		border-radius: 8px;
		padding: 7px 10px;
		font: inherit;
		font-size: 13px;
		width: 100%;
		box-sizing: border-box;
	}

	.text-input:focus {
		outline: none;
		border-color: rgba(74, 144, 217, 0.4);
	}

	/* ── Calibration toggle ────────────────────────────────────────────────── */
	.calibration-field {
		justify-content: flex-start;
	}

	.toggle-label {
		display: flex;
		align-items: center;
		gap: 8px;
		cursor: pointer;
		padding-top: 4px;
	}

	.toggle-input {
		position: absolute;
		opacity: 0;
		width: 0;
		height: 0;
	}

	.toggle-track {
		position: relative;
		display: inline-block;
		width: 32px;
		height: 18px;
		border-radius: 9px;
		background: rgba(255, 255, 255, 0.08);
		border: 1px solid rgba(255, 255, 255, 0.12);
		transition: background 0.15s, border-color 0.15s;
		flex-shrink: 0;
	}

	.toggle-track.checked {
		background: rgba(214, 158, 46, 0.2);
		border-color: rgba(214, 158, 46, 0.45);
	}

	.toggle-thumb {
		position: absolute;
		top: 2px;
		left: 2px;
		width: 12px;
		height: 12px;
		border-radius: 50%;
		background: #4a5568;
		transition: transform 0.15s, background 0.15s;
	}

	.toggle-track.checked .toggle-thumb {
		transform: translateX(14px);
		background: #d6a030;
	}

	.toggle-text {
		font-family: 'DM Mono', monospace;
		font-size: 12px;
		color: #6b8292;
		letter-spacing: 0.04em;
	}

	/* ── Confounders (post_run_fields) ─────────────────────────────────────── */
	.confounders-section {
		display: grid;
		gap: 8px;
	}

	.section-label {
		font-family: 'DM Mono', monospace;
		font-size: 10px;
		letter-spacing: 0.16em;
		text-transform: uppercase;
		color: #4a5568;
	}

	.confounders-grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
		gap: 8px;
	}
</style>
