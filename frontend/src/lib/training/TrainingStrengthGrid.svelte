<script lang="ts">
	/**
	 * TrainingStrengthGrid — the whole-session strength table for a v3 strength card.
	 *
	 * Read-primary layout: one aligned row per exercise (Exercise · Target · Last), so a
	 * whole session is scannable at a glance and the prescription — not an empty input grid —
	 * is the dominant content. `Target` is built from the structured prescription fields
	 * (`sets`, `reps_low`/`reps_high`, `load_kind`/`load_value`, `tempo`); `Last` is the
	 * backend-provided load anchor (`ex.last`, the most recent logged set). The first exercise
	 * is emphasised as the session's anchor lift.
	 *
	 * log mode: for exercises the card flags `log_sets`, a compact per-set weight/reps/RIR grid
	 * appears as a secondary row beneath the exercise, seeded once from `card.capture.set_logs`
	 * (matched by `exercise_id`), one blank row per prescribed set when nothing was logged yet,
	 * plus an add-set button. Guarded `oninput` handlers write into the tracked `$state` array
	 * directly — never a deep `bind:` into the nested `#each` (Svelte 5 nested-each writeback bug).
	 *
	 * Capture ownership: this component owns ONLY `set_logs`. It emits just that slice via
	 * `onSetLogs` on every change and never reads or replays `checkin`/`rpe` — TrainingCardBody
	 * composes the full TrainingCaptureLog from each child's slice.
	 */
	import { untrack } from 'svelte';
	import type { TrainingCaptureLog, TrainingExerciseDisplay, TrainingExerciseLog, TrainingSetLog } from '$lib/api';

	let {
		card,
		mode,
		onSetLogs
	}: {
		card: { exercises_display: TrainingExerciseDisplay[]; capture: TrainingCaptureLog | null };
		mode: 'log' | 'view';
		onSetLogs?: (setLogs: TrainingCaptureLog['set_logs']) => void;
	} = $props();

	const exercises = $derived(card.exercises_display);

	// ── One-time synchronous init — never re-runs when card.capture changes. The component
	// is freshly mounted each time a detail panel opens, so reading card.capture once at
	// construction is correct and sufficient.
	const initialExercises = untrack(() => card.exercises_display);
	const initialCapture = untrack(() => card.capture);

	function emptySet(index: number): TrainingSetLog {
		return { set_index: index, weight: null, reps: null, rir: null };
	}

	/** Restore logged sets for one exercise, or one blank row per prescribed set. */
	function seedSets(exercise: TrainingExerciseDisplay): TrainingSetLog[] {
		const logged = initialCapture?.set_logs.find((log) => log.exercise_id === exercise.exercise_id);
		if (logged && logged.sets.length > 0) {
			return logged.sets.map((s) => ({
				set_index: s.set_index,
				weight: s.weight,
				reps: s.reps,
				rir: s.rir
			}));
		}
		const count = Math.max(1, exercise.sets);
		return Array.from({ length: count }, (_, i) => emptySet(i));
	}

	// Only exercises the card marks log_sets get an entry — the others are pure display.
	let exerciseLogs = $state<TrainingExerciseLog[]>(
		initialExercises
			.filter((ex) => ex.log_sets)
			.map((ex) => ({ exercise_id: ex.exercise_id, sets: seedSets(ex) }))
	);

	function logIndexOf(exerciseId: string): number {
		return exerciseLogs.findIndex((log) => log.exercise_id === exerciseId);
	}

	function setsFor(exerciseId: string): TrainingSetLog[] {
		return exerciseLogs[logIndexOf(exerciseId)]?.sets ?? [];
	}

	function addSet(exerciseId: string) {
		const idx = logIndexOf(exerciseId);
		if (idx === -1) return;
		const nextIndex = exerciseLogs[idx].sets.length;
		exerciseLogs[idx].sets = [...exerciseLogs[idx].sets, emptySet(nextIndex)];
		emit();
	}

	function setSetField(
		exerciseId: string,
		setIdx: number,
		field: 'weight' | 'reps' | 'rir',
		raw: string
	) {
		const idx = logIndexOf(exerciseId);
		const set = exerciseLogs[idx]?.sets[setIdx];
		if (!set) return;
		const num = raw === '' ? null : Number(raw);
		set[field] = num !== null && Number.isFinite(num) ? num : null;
		emit();
	}

	function emit() {
		onSetLogs?.(exerciseLogs);
	}

	// ── Presentation helpers (display-only formatting of backend-provided fields) ──────────
	function trimNum(n: number): string {
		// JS already renders 8.0 as "8"; kept as a seam for future unit formatting.
		return String(n);
	}

	function formatReps(ex: TrainingExerciseDisplay): string {
		return ex.reps_low === ex.reps_high ? `${ex.reps_low}` : `${ex.reps_low}–${ex.reps_high}`;
	}

	function formatLoad(ex: TrainingExerciseDisplay): string {
		if (ex.load_kind === 'rpe' && ex.load_value != null) return `@${trimNum(ex.load_value)}`;
		if (ex.load_kind === 'pct_e1rm' && ex.load_value != null) return `@${Math.round(ex.load_value * 100)}%`;
		if (ex.load_kind === 'absolute_kg' && ex.load_value != null) return `${trimNum(ex.load_value)}kg`;
		return '';
	}

	function formatLast(last: TrainingExerciseDisplay['last']): string {
		if (!last) return '—';
		if (last.weight_kg != null && last.reps != null) return `${trimNum(last.weight_kg)}×${last.reps}`;
		if (last.weight_kg != null) return `${trimNum(last.weight_kg)}kg`;
		if (last.reps != null) return `${last.reps} reps`;
		return '—';
	}
</script>

<div class="session-table" role="table">
	<div class="row head" role="row">
		<span class="dot" aria-hidden="true"></span>
		<span class="col-ex" role="columnheader">Exercise</span>
		<span class="col-tgt" role="columnheader">Target</span>
		<span class="col-last" role="columnheader">Last</span>
	</div>

	{#each exercises as ex, i (ex.exercise_id)}
		<div class="row" class:anchor={i === 0} role="row">
			<span class="dot" aria-hidden="true">{i === 0 ? '●' : '○'}</span>
			<span class="col-ex" role="cell">
				<span class="ex-name">{ex.name}</span>
				{#if i === 0}<span class="anchor-tag">anchor</span>{/if}
				{#if ex.tempo}<span class="cue">{ex.tempo}</span>{/if}
			</span>
			<span class="col-tgt" role="cell">
				<span class="tgt-main">{ex.sets}×{formatReps(ex)}</span>
				{#if formatLoad(ex)}<span class="load">{formatLoad(ex)}</span>{/if}
			</span>
			<span class="col-last" role="cell">{formatLast(ex.last)}</span>
		</div>

		{#if mode === 'log' && ex.log_sets}
			<div class="log-panel" role="row">
				<div class="set-grid">
					{#each setsFor(ex.exercise_id) as set, setIdx (setIdx)}
						<div class="set-line">
							<span class="set-n">{set.set_index + 1}</span>
							<input
								type="number"
								class="set-input"
								value={set.weight ?? ''}
								oninput={(e) => setSetField(ex.exercise_id, setIdx, 'weight', e.currentTarget.value)}
								placeholder="kg"
								min={0}
								step={0.5}
								aria-label="weight"
							/>
							<input
								type="number"
								class="set-input"
								value={set.reps ?? ''}
								oninput={(e) => setSetField(ex.exercise_id, setIdx, 'reps', e.currentTarget.value)}
								placeholder="reps"
								min={0}
								aria-label="reps"
							/>
							<input
								type="number"
								class="set-input"
								value={set.rir ?? ''}
								oninput={(e) => setSetField(ex.exercise_id, setIdx, 'rir', e.currentTarget.value)}
								placeholder="rir"
								min={0}
								max={10}
								aria-label="reps in reserve"
							/>
						</div>
					{/each}
					<button type="button" class="add-set-btn" onclick={() => addSet(ex.exercise_id)}>+ set</button>
				</div>
			</div>
		{/if}
	{/each}
</div>

<style>
	.session-table {
		display: grid;
		gap: 0;
	}

	.row {
		display: grid;
		grid-template-columns: 16px 1fr auto auto;
		align-items: baseline;
		gap: 10px;
		padding: 9px 2px;
		border-bottom: 1px solid rgba(255, 255, 255, 0.05);
	}

	.row.head {
		padding: 4px 2px;
		border-bottom: 1px solid rgba(255, 255, 255, 0.09);
	}

	.row.head span {
		font-family: 'DM Mono', monospace;
		font-size: 10px;
		letter-spacing: 0.08em;
		text-transform: uppercase;
		color: #4a5568;
	}

	.dot {
		color: #3a4658;
		font-size: 9px;
		line-height: 1;
	}
	.row.anchor .dot {
		color: #d9a441;
	}

	.col-ex {
		display: flex;
		flex-wrap: wrap;
		align-items: baseline;
		gap: 6px;
		min-width: 0;
	}
	.ex-name {
		color: #c5d8e4;
		font-size: 13.5px;
		font-weight: 500;
	}
	.row.anchor .ex-name {
		color: #eef5f8;
		font-weight: 600;
	}
	.anchor-tag {
		font-family: 'DM Mono', monospace;
		font-size: 9px;
		letter-spacing: 0.06em;
		text-transform: uppercase;
		color: #d9a441;
		background: rgba(217, 164, 65, 0.12);
		border-radius: 4px;
		padding: 1px 5px;
	}
	.cue {
		flex-basis: 100%;
		color: #6b8292;
		font-size: 11px;
		line-height: 1.3;
	}

	.col-tgt {
		text-align: right;
		white-space: nowrap;
		color: #eef5f8;
		font-size: 13.5px;
		font-variant-numeric: tabular-nums;
	}
	/* Structured reps + a visually-hidden "sets×reps" for screen readers; the sighted
	   value shows sets via the reps element's ::before to keep tabular alignment simple. */
	.tgt-main {
		font-weight: 700;
	}
	.load {
		color: #8fa3b0;
		font-size: 12.5px;
		margin-left: 3px;
	}

	.col-last {
		text-align: right;
		white-space: nowrap;
		color: #8fa3b0;
		font-size: 12.5px;
		font-variant-numeric: tabular-nums;
		min-width: 44px;
	}

	/* ── Compact per-set log panel (secondary) ─────────────────────────────────── */
	.log-panel {
		padding: 6px 2px 10px 26px;
		border-bottom: 1px solid rgba(255, 255, 255, 0.05);
	}
	.set-grid {
		display: flex;
		flex-direction: column;
		gap: 4px;
		align-items: flex-start;
	}
	.set-line {
		display: grid;
		grid-template-columns: 18px 56px 56px 56px;
		gap: 6px;
		align-items: center;
	}
	.set-n {
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
		padding: 4px 6px;
		font: inherit;
		font-size: 12px;
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
	.set-input::placeholder {
		color: #3a4658;
	}
	.set-input:focus {
		outline: none;
		border-color: rgba(74, 144, 217, 0.4);
	}
	.add-set-btn {
		padding: 3px 9px;
		border-radius: 6px;
		border: 1px dashed rgba(255, 255, 255, 0.12);
		background: transparent;
		color: #4a5568;
		font: inherit;
		font-size: 11px;
		font-family: 'DM Mono', monospace;
		cursor: pointer;
		transition: color 0.15s, border-color 0.15s;
	}
	.add-set-btn:hover {
		color: #c5d8e4;
		border-color: rgba(255, 255, 255, 0.25);
	}
</style>
