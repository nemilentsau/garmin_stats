<script lang="ts">
	/**
	 * TrainingStrengthGrid — per-exercise set-logging grid for a v3 strength card.
	 *
	 * view mode: exercise name + scheme chip + tempo detail only — no captured-set display,
	 * mirroring StrengthSessionCard's view-mode simplicity (Schedule shows the prescription,
	 * not history).
	 *
	 * log mode: for exercises the card flags `log_sets`, a per-set weight/reps/RIR grid
	 * seeded once from `card.capture.set_logs` (matched by `exercise_id`), pre-filled with
	 * one blank row per prescribed set when nothing was logged yet, plus an add-set button
	 * for sets beyond the prescription. Guarded `oninput` handlers write into the tracked
	 * `$state` array directly — never a deep `bind:` into the nested `#each`, matching
	 * StrengthSessionCard's per-set grid (Svelte 5 nested-each writeback bug).
	 *
	 * Every change emits the FULL TrainingCaptureLog: `set_logs` reflects the live edit,
	 * `checkin`/`rpe` pass through untouched from this component's own once-only seed. The
	 * shipped v3 bundles never combine a `set_rep_load[]` capture field with checkin or rpe
	 * fields on the same card (see `docs/routine-pivot/block0/*.json`), so that passthrough
	 * never goes stale in practice; TrainingCardBody still re-mirrors whichever capture
	 * arrives last, so this stays correct even if that assumption changes.
	 */
	import { untrack } from 'svelte';
	import type {
		TrainingCaptureLog,
		TrainingExerciseDisplay,
		TrainingExerciseLog,
		TrainingSetLog
	} from '$lib/api';

	let {
		card,
		mode,
		onCapture
	}: {
		card: { exercises_display: TrainingExerciseDisplay[]; capture: TrainingCaptureLog | null };
		mode: 'log' | 'view';
		onCapture?: (capture: TrainingCaptureLog) => void;
	} = $props();

	const exercises = $derived(card.exercises_display);

	// ── One-time synchronous init — never re-runs when card.capture changes. The component
	// is freshly mounted each time a detail panel opens, so reading card.capture once at
	// construction is correct and sufficient (see StrengthSessionCard for the same pattern).
	const initialExercises = untrack(() => card.exercises_display);
	const initialCapture = untrack(() => card.capture);
	const seedCheckin = initialCapture?.checkin ?? null;
	const seedRpe = initialCapture?.rpe ?? null;

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
		onCapture?.({
			set_logs: exerciseLogs,
			checkin: seedCheckin,
			rpe: seedRpe
		});
	}
</script>

<div class="exercise-list">
	{#each exercises as ex}
		<div class="exercise-block">
			<div class="ex-header-row">
				<span class="ex-name">{ex.name}</span>
				<span class="scheme-badge">{ex.scheme}</span>
			</div>
			{#if ex.tempo}
				<span class="ex-detail">Tempo {ex.tempo}</span>
			{/if}

			{#if mode === 'log' && ex.log_sets}
				<div class="set-table">
					<div class="set-header-row">
						<span class="col-set">Set</span>
						<span class="col-num">Weight</span>
						<span class="col-num">Reps</span>
						<span class="col-num">RIR</span>
					</div>
					{#each setsFor(ex.exercise_id) as set, setIdx}
						<div class="set-data-row">
							<span class="col-set set-num">{set.set_index + 1}</span>
							<input
								type="number"
								class="col-num set-input"
								value={set.weight ?? ''}
								oninput={(e) => setSetField(ex.exercise_id, setIdx, 'weight', e.currentTarget.value)}
								placeholder="—"
								min={0}
								step={0.5}
							/>
							<input
								type="number"
								class="col-num set-input"
								value={set.reps ?? ''}
								oninput={(e) => setSetField(ex.exercise_id, setIdx, 'reps', e.currentTarget.value)}
								placeholder="—"
								min={0}
							/>
							<input
								type="number"
								class="col-num set-input"
								value={set.rir ?? ''}
								oninput={(e) => setSetField(ex.exercise_id, setIdx, 'rir', e.currentTarget.value)}
								placeholder="—"
								min={0}
								max={10}
							/>
						</div>
					{/each}
				</div>
				<button type="button" class="add-set-btn" onclick={() => addSet(ex.exercise_id)}>
					+ Add set
				</button>
			{/if}
		</div>
	{/each}
</div>

<style>
	.exercise-list {
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
	}

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

	/* ── Per-set grid ──────────────────────────────────────────────────────── */
	.set-table {
		display: grid;
		gap: 3px;
	}

	.set-header-row,
	.set-data-row {
		display: grid;
		grid-template-columns: 28px 1fr 1fr 1fr;
		gap: 6px;
		align-items: center;
	}

	.set-header-row {
		padding: 0 2px 2px;
		border-bottom: 1px solid rgba(255, 255, 255, 0.06);
	}

	.col-set,
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
		transition:
			color 0.15s,
			border-color 0.15s;
	}

	.add-set-btn:hover {
		color: #c5d8e4;
		border-color: rgba(255, 255, 255, 0.25);
	}
</style>
