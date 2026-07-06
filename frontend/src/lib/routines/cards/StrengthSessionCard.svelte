<script lang="ts">
	/**
	 * StrengthSessionCard — dedicated card for strength_session payloads.
	 *
	 * view mode: session focus, duration, RIR guidance, instructions, and each prescribed
	 * exercise with its set_scheme and detail — read-only summary for Schedule.
	 *
	 * log mode: per-exercise table of {weight, reps, RIR} inputs with add/remove set controls;
	 * an "+ Add extra exercise" affordance that appends a LoggedStrengthExercise with
	 * is_extra=true and a free-text label; rating inputs. Emits StrengthActual on every change.
	 * Prefills from existing card.actual_json when the card_type matches.
	 *
	 * No statistical computation here — volume, totals, etc. are backend concerns.
	 */
	import { untrack } from 'svelte';
	import type { ScheduleOccurrence, TodayCard } from '$lib/api';
	import { buildInitialRatings, cleanRatings } from './rating-helpers.js';
	import RatingsGrid from './RatingsGrid.svelte';
	import {
		buildInitialExercises,
		serializeExercises,
		type LoggedStrengthExercise,
		type StrengthSetLog
	} from './strength-helpers.js';

	type StrengthPayload = Extract<
		ScheduleOccurrence['payload_json'],
		{ card_type: 'strength_session' }
	>;
	type FullActual = TodayCard['actual_json'];

	export type StrengthActual = {
		card_type: 'strength_session';
		exercises: LoggedStrengthExercise[];
		ratings: Record<string, number>;
	};

	let {
		card,
		mode,
		onActual
	}: {
		card: { payload_json: StrengthPayload; actual_json?: FullActual };
		mode: 'log' | 'view';
		onActual?: (actual: StrengthActual) => void;
	} = $props();

	const payload = $derived(card.payload_json);
	const prescribed = $derived(payload.exercises ?? []);
	const prompts = $derived(payload.rating_prompts ?? []);

	// ── One-time synchronous init — never re-runs when actual_json changes ────
	// The component is freshly mounted each time a detail panel opens ({#if isExpanded}),
	// so reading card.actual_json once at construction is correct and sufficient.
	// Using untrack prevents the surrounding reactive context from tracking actual_json.
	const initialActual = untrack(() =>
		card.actual_json?.card_type === 'strength_session' ? card.actual_json : null
	);
	const initialPrescribed = untrack(() => card.payload_json.exercises ?? []);
	const initialPrompts = untrack(() => card.payload_json.rating_prompts ?? []);

	// ── Mutable log state ─────────────────────────────────────────────────────
	let exercises = $state<LoggedStrengthExercise[]>(
		buildInitialExercises(initialPrescribed, initialActual)
	);
	let ratings = $state<Record<string, number | null>>(
		buildInitialRatings(initialPrompts, initialActual?.ratings)
	);

	// ── Set / exercise helpers ─────────────────────────────────────────────────

	function addSet(exIdx: number) {
		const nextIdx = exercises[exIdx].sets.length;
		exercises[exIdx].sets = [
			...exercises[exIdx].sets,
			{ set_index: nextIdx, weight: null, reps: null, rir: null }
		];
		emit();
	}

	function removeSet(exIdx: number, setIdx: number) {
		const kept = exercises[exIdx].sets.filter((_, i) => i !== setIdx);
		exercises[exIdx].sets = kept.map((s, i) => ({ ...s, set_index: i }));
		emit();
	}

	// Write a numeric set field by index. Using an explicit guarded handler
	// (instead of `bind:value` on a deep index path) keeps the write on the
	// tracked `$state` proxy and avoids Svelte 5's deep-bind setter throwing
	// "Cannot set properties of undefined" during each-block reconciliation.
	function setSetField(exIdx: number, setIdx: number, field: 'weight' | 'reps' | 'rir', raw: string) {
		const set = exercises[exIdx]?.sets[setIdx];
		if (!set) return;
		const num = raw === '' ? null : Number(raw);
		set[field] = num !== null && Number.isFinite(num) ? num : null;
		emit();
	}

	function addExtra() {
		exercises = [
			...exercises,
			{
				exercise_id: null,
				label: null,
				is_extra: true,
				sets: [{ set_index: 0, weight: null, reps: null, rir: null }]
			}
		];
		// No emit yet — label is empty; the user must type a name first.
	}

	function removeExtra(exIdx: number) {
		exercises = exercises.filter((_, i) => i !== exIdx);
		emit();
	}

	// ── Emit ──────────────────────────────────────────────────────────────────

	function emit() {
		onActual?.({
			card_type: 'strength_session',
			exercises: serializeExercises(exercises),
			ratings: cleanRatings(ratings)
		});
	}

	// ── Display helpers ────────────────────────────────────────────────────────

	/** Return the display label for an exercise entry (prescribed or extra). */
	function exerciseDisplayLabel(ex: LoggedStrengthExercise): string {
		if (ex.label) return ex.label;
		if (!ex.is_extra) {
			const p = prescribed.find((p) => p.id === ex.exercise_id);
			return p?.label ?? '—';
		}
		return '';
	}

	/** Return the set_scheme for a prescribed exercise, if available. */
	function setScheme(exIdx: number): string | null {
		const ex = exercises[exIdx];
		if (ex.is_extra) return null;
		const p = prescribed.find((p) => p.id === ex.exercise_id);
		return p?.set_scheme ?? null;
	}
</script>

{#if payload.instructions}
	<p class="detail-copy">{payload.instructions}</p>
{/if}

{#if mode === 'view'}
	<!-- ── VIEW MODE ─────────────────────────────────────────────────────────── -->
	<div class="meta-row">
		{#if payload.session_focus}
			<span class="badge focus-badge">{payload.session_focus}</span>
		{/if}
		{#if payload.duration_minutes}
			<span class="duration-label">{payload.duration_minutes} min</span>
		{/if}
		{#if payload.rir_guidance}
			<span class="rir-label">RIR: {payload.rir_guidance}</span>
		{/if}
	</div>

	{#if prescribed.length > 0}
		<div class="exercise-list">
			{#each prescribed as ex}
				<div class="exercise-view-row">
					<div class="ex-header-row">
						<span class="ex-name">{ex.label}</span>
						<span class="scheme-badge">{ex.set_scheme}</span>
					</div>
					{#if ex.detail}
						<span class="ex-detail">{ex.detail}</span>
					{/if}
				</div>
			{/each}
		</div>
	{/if}
{:else}
	<!-- ── LOG MODE ──────────────────────────────────────────────────────────── -->
	<div class="meta-row">
		{#if payload.session_focus}
			<span class="badge focus-badge">{payload.session_focus}</span>
		{/if}
		{#if payload.duration_minutes}
			<span class="duration-label">{payload.duration_minutes} min</span>
		{/if}
		{#if payload.rir_guidance}
			<span class="rir-label">RIR target: {payload.rir_guidance}</span>
		{/if}
	</div>

	<!-- Exercises (prescribed + extras) -->
	<div class="exercises-section">
		{#each exercises as ex, exIdx}
			{@const prescribedRef = !ex.is_extra ? prescribed.find((p) => p.id === ex.exercise_id) : null}
			<div class="exercise-block" class:is-extra={ex.is_extra}>
				<!-- Exercise header -->
				<div class="ex-header-row">
					{#if ex.is_extra}
						<span class="extra-badge">extra</span>
						<input
							type="text"
							class="extra-label-input"
							bind:value={ex.label}
							placeholder="Exercise name…"
							onblur={emit}
							onchange={emit}
						/>
						<button
							class="remove-btn"
							aria-label="Remove extra exercise"
							onclick={() => removeExtra(exIdx)}>✕</button
						>
					{:else}
						<span class="ex-name">{exerciseDisplayLabel(ex)}</span>
						{#if setScheme(exIdx)}
							<span class="scheme-badge">{setScheme(exIdx)}</span>
						{/if}
					{/if}
				</div>

				{#if prescribedRef?.detail}
					<span class="ex-detail">{prescribedRef.detail}</span>
				{/if}

				<!-- Per-set grid -->
				<div class="set-table">
					<div class="set-header-row">
						<span class="col-set">Set</span>
						<span class="col-num">Weight</span>
						<span class="col-num">Reps</span>
						<span class="col-num">RIR</span>
						<span class="col-action"></span>
					</div>
					{#each ex.sets as set, setIdx}
						<div class="set-data-row">
							<span class="col-set set-num">{set.set_index + 1}</span>
							<input
								type="number"
								class="col-num set-input"
								value={set.weight ?? ''}
								oninput={(e) => setSetField(exIdx, setIdx, 'weight', e.currentTarget.value)}
								placeholder="—"
								min={0}
								step={0.5}
							/>
							<input
								type="number"
								class="col-num set-input"
								value={set.reps ?? ''}
								oninput={(e) => setSetField(exIdx, setIdx, 'reps', e.currentTarget.value)}
								placeholder="—"
								min={0}
							/>
							<input
								type="number"
								class="col-num set-input"
								value={set.rir ?? ''}
								oninput={(e) => setSetField(exIdx, setIdx, 'rir', e.currentTarget.value)}
								placeholder="—"
								min={0}
								max={10}
							/>
							<button
								class="col-action remove-set-btn"
								aria-label="Remove set {set.set_index + 1}"
								onclick={() => removeSet(exIdx, setIdx)}
								disabled={ex.sets.length <= 1}>✕</button
							>
						</div>
					{/each}
				</div>

				<button class="add-set-btn" onclick={() => addSet(exIdx)}>+ Add set</button>
			</div>
		{/each}

		<!-- Add extra exercise -->
		<button class="add-extra-btn" onclick={addExtra}>+ Add extra exercise</button>
	</div>

	<RatingsGrid {prompts} bind:ratings onCommit={emit} />
{/if}

<style>
	.detail-copy {
		margin: 0;
		color: #a7bac6;
		font-size: 13px;
		line-height: 1.5;
	}

	/* Meta row */
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

	.focus-badge {
		text-transform: uppercase;
		letter-spacing: 0.1em;
	}

	.duration-label {
		color: #6b8292;
		font-size: 12px;
		font-family: 'DM Mono', monospace;
		letter-spacing: 0.08em;
	}

	.rir-label {
		color: #6b8292;
		font-size: 11px;
		font-family: 'DM Mono', monospace;
		letter-spacing: 0.06em;
	}

	/* ── View mode ─────────────────────────────────────────────────────────── */
	.exercise-list {
		display: grid;
		gap: 6px;
	}

	.exercise-view-row {
		display: flex;
		flex-direction: column;
		gap: 3px;
		padding: 8px 10px;
		border-radius: 8px;
		background: rgba(255, 255, 255, 0.03);
	}

	/* ── Shared exercise header ────────────────────────────────────────────── */
	.ex-header-row {
		display: flex;
		align-items: center;
		gap: 8px;
		flex-wrap: wrap;
	}

	.ex-name {
		color: #c5d8e4;
		font-size: 13px;
		font-weight: 500;
	}

	.scheme-badge {
		font-family: 'DM Mono', monospace;
		font-size: 11px;
		color: #6b8292;
		background: rgba(255, 255, 255, 0.05);
		border: 1px solid rgba(255, 255, 255, 0.08);
		border-radius: 4px;
		padding: 2px 6px;
	}

	.ex-detail {
		color: #6b8292;
		font-size: 11px;
		line-height: 1.4;
	}

	/* ── Log mode exercises ────────────────────────────────────────────────── */
	.exercises-section {
		display: grid;
		gap: 10px;
	}

	.exercise-block {
		display: flex;
		flex-direction: column;
		gap: 6px;
		padding: 10px;
		border-radius: 8px;
		background: rgba(255, 255, 255, 0.03);
		border: 1px solid transparent;
	}

	.exercise-block.is-extra {
		border-color: rgba(168, 112, 255, 0.2);
		background: rgba(168, 112, 255, 0.04);
	}

	/* Extra exercise badge */
	.extra-badge {
		display: inline-block;
		padding: 2px 6px;
		border-radius: 4px;
		background: rgba(168, 112, 255, 0.15);
		border: 1px solid rgba(168, 112, 255, 0.3);
		color: #a870ff;
		font-family: 'DM Mono', monospace;
		font-size: 10px;
		letter-spacing: 0.1em;
		text-transform: uppercase;
		flex-shrink: 0;
	}

	.extra-label-input {
		flex: 1;
		min-width: 120px;
		border: 1px solid rgba(168, 112, 255, 0.25);
		background: rgba(8, 15, 24, 0.7);
		color: #c5d8e4;
		border-radius: 6px;
		padding: 4px 8px;
		font: inherit;
		font-size: 13px;
		font-weight: 500;
	}

	.extra-label-input:focus {
		outline: none;
		border-color: rgba(168, 112, 255, 0.5);
	}

	.remove-btn {
		padding: 2px 6px;
		border: none;
		background: transparent;
		color: #4a5568;
		font-size: 11px;
		cursor: pointer;
		border-radius: 4px;
		margin-left: auto;
		transition: color 0.15s;
	}

	.remove-btn:hover {
		color: #e57373;
	}

	/* ── Per-set grid ──────────────────────────────────────────────────────── */
	.set-table {
		display: grid;
		gap: 3px;
	}

	.set-header-row,
	.set-data-row {
		display: grid;
		grid-template-columns: 28px 1fr 1fr 1fr 24px;
		gap: 6px;
		align-items: center;
	}

	.set-header-row {
		padding: 0 2px 2px;
		border-bottom: 1px solid rgba(255, 255, 255, 0.06);
	}

	.col-set {
		font-family: 'DM Mono', monospace;
		font-size: 10px;
		letter-spacing: 0.1em;
		text-transform: uppercase;
		color: #4a5568;
		text-align: center;
	}

	.col-num {
		font-family: 'DM Mono', monospace;
		font-size: 10px;
		letter-spacing: 0.1em;
		text-transform: uppercase;
		color: #4a5568;
		text-align: center;
	}

	.set-num {
		font-family: 'DM Mono', monospace;
		font-size: 11px;
		color: #4a5568;
		text-align: center;
		font-variant-numeric: tabular-nums;
	}

	.set-input {
		border: 1px solid rgba(255, 255, 255, 0.08);
		background: rgba(8, 15, 24, 0.7);
		color: #eef5f8;
		border-radius: 6px;
		padding: 5px 6px;
		font: inherit;
		font-size: 13px;
		font-family: 'DM Mono', monospace;
		font-variant-numeric: tabular-nums;
		text-align: center;
		width: 100%;
		box-sizing: border-box;
		appearance: textfield;
		-moz-appearance: textfield;
	}

	.set-input::-webkit-outer-spin-button,
	.set-input::-webkit-inner-spin-button {
		-webkit-appearance: none;
		margin: 0;
	}

	.set-input:focus {
		outline: none;
		border-color: rgba(74, 144, 217, 0.4);
	}

	.remove-set-btn {
		border: none;
		background: transparent;
		color: #2d3748;
		font-size: 10px;
		cursor: pointer;
		padding: 4px;
		border-radius: 4px;
		transition: color 0.15s;
		display: flex;
		align-items: center;
		justify-content: center;
	}

	.remove-set-btn:not(:disabled):hover {
		color: #e57373;
	}

	.remove-set-btn:disabled {
		opacity: 0.2;
		cursor: not-allowed;
	}

	/* Add set / add extra buttons */
	.add-set-btn {
		align-self: flex-start;
		padding: 4px 10px;
		border-radius: 6px;
		border: 1px dashed rgba(255, 255, 255, 0.12);
		background: transparent;
		color: #4a5568;
		font: inherit;
		font-size: 11px;
		font-family: 'DM Mono', monospace;
		letter-spacing: 0.06em;
		cursor: pointer;
		transition: color 0.15s, border-color 0.15s;
	}

	.add-set-btn:hover {
		color: #c5d8e4;
		border-color: rgba(255, 255, 255, 0.25);
	}

	.add-extra-btn {
		padding: 7px 14px;
		border-radius: 7px;
		border: 1px dashed rgba(168, 112, 255, 0.3);
		background: rgba(168, 112, 255, 0.04);
		color: #a870ff;
		font: inherit;
		font-size: 12px;
		font-family: 'DM Mono', monospace;
		letter-spacing: 0.06em;
		cursor: pointer;
		transition: background 0.15s, border-color 0.15s;
		align-self: flex-start;
	}

	.add-extra-btn:hover {
		background: rgba(168, 112, 255, 0.1);
		border-color: rgba(168, 112, 255, 0.5);
	}

</style>
