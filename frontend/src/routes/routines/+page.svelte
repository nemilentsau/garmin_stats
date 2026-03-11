<script lang="ts">
	import { onMount } from 'svelte';
	import {
		api,
		type DailyCheckIn,
		type DailyCheckInInput,
		type Note,
		type NoteInput,
		type Routine,
		type RoutineEntry,
		type RoutineEntryInput,
		type RoutineInput
	} from '$lib/api';
	import { COLORS } from '$lib/colors';
	import { errorMessage, makeId } from '$lib/utils';

	type RoutineCategory = 'mindfulness' | 'nutrition' | 'strength' | 'mobility' | 'sleep' | 'recovery' | 'custom';

	const categoryAccent: Record<string, string> = {
		mindfulness: COLORS.hrv,
		nutrition: COLORS.skinTemp,
		strength: COLORS.heartRate,
		mobility: COLORS.respiration,
		sleep: COLORS.sleep,
		recovery: COLORS.bodyBattery,
		custom: '#8a9baa'
	};

	const categoryOptions: RoutineCategory[] = [
		'mindfulness',
		'nutrition',
		'strength',
		'mobility',
		'sleep',
		'recovery',
		'custom'
	];

	const unitOptions = ['boolean', 'minutes', 'sets', 'grams', 'rating'];

	let loading = $state(true);
	let saving = $state(false);
	let error: string | null = $state(null);

	let selectedDate = $state(new Date().toISOString().slice(0, 10));
	let routines: Routine[] = $state([]);
	let entries: RoutineEntry[] = $state([]);
	let notes: Note[] = $state([]);
	let selectedRoutineId = $state('');
	let checkinExists = $state(false);

	let routineForm = $state<Required<Pick<RoutineInput, 'id' | 'name' | 'category' | 'status' | 'description' | 'default_unit' | 'target_frequency' | 'default_time_of_day' | 'tags' | 'linked_goal_ids'>>>({
		id: '',
		name: '',
		category: 'mindfulness',
		status: 'active',
		description: '',
		default_unit: 'boolean',
		target_frequency: '',
		default_time_of_day: '',
		tags: [],
		linked_goal_ids: []
	});

	let entryForm = $state<Required<Pick<RoutineEntryInput, 'id' | 'routine_id' | 'date' | 'timestamp_local' | 'value_numeric' | 'value_text' | 'completion_state' | 'source' | 'notes'>>>({
		id: '',
		routine_id: '',
		date: '',
		timestamp_local: '',
		value_numeric: null,
		value_text: '',
		completion_state: 'completed',
		source: 'manual',
		notes: ''
	});

	let checkinForm = $state<Required<DailyCheckInInput>>({
		id: '',
		date: '',
		energy: null,
		mood: null,
		motivation: null,
		soreness: null,
		stress_subjective: null,
		sleep_quality_subjective: null,
		workload_subjective: null,
		illness_flag: false,
		travel_flag: false,
		alcohol_flag: false,
		notes: ''
	});

	let noteForm = $state<Required<NoteInput>>({
		id: '',
		date: '',
		category: 'reflection',
		title: '',
		content: '',
		tags: []
	});

	function resetCheckinForm(date: string) {
		checkinForm.id = `checkin-${date}`;
		checkinForm.date = date;
		checkinForm.energy = null;
		checkinForm.mood = null;
		checkinForm.motivation = null;
		checkinForm.soreness = null;
		checkinForm.stress_subjective = null;
		checkinForm.sleep_quality_subjective = null;
		checkinForm.workload_subjective = null;
		checkinForm.illness_flag = false;
		checkinForm.travel_flag = false;
		checkinForm.alcohol_flag = false;
		checkinForm.notes = '';
	}

	function applyCheckinForm(checkin: DailyCheckIn | null, date: string) {
		if (!checkin) {
			resetCheckinForm(date);
			return;
		}

		checkinForm.id = checkin.id;
		checkinForm.date = checkin.date;
		checkinForm.energy = checkin.energy;
		checkinForm.mood = checkin.mood;
		checkinForm.motivation = checkin.motivation;
		checkinForm.soreness = checkin.soreness;
		checkinForm.stress_subjective = checkin.stress_subjective;
		checkinForm.sleep_quality_subjective = checkin.sleep_quality_subjective;
		checkinForm.workload_subjective = checkin.workload_subjective;
		checkinForm.illness_flag = checkin.illness_flag;
		checkinForm.travel_flag = checkin.travel_flag;
		checkinForm.alcohol_flag = checkin.alcohol_flag;
		checkinForm.notes = checkin.notes ?? '';
	}

	async function loadPageData() {
		error = null;
		const [daysResponse, routinesResponse] = await Promise.all([api.getDays(), api.getRoutines()]);
		const latestDay = daysResponse.days[daysResponse.days.length - 1];
		if (latestDay) {
			selectedDate = latestDay;
		}
		routines = routinesResponse.routines;
		if (!selectedRoutineId && routines.length > 0) {
			selectedRoutineId = routines[0].id;
		}
	}

	async function loadDailySidecars() {
		const [notesResponse, checkinsResponse] = await Promise.all([
			api.getNotes(selectedDate),
			api.getCheckins(selectedDate)
		]);
		notes = notesResponse.notes;
		const existingCheckin = checkinsResponse.checkins[0] ?? null;
		checkinExists = existingCheckin !== null;
		applyCheckinForm(existingCheckin, selectedDate);
	}

	onMount(() => {
		void loadPageData()
			.catch((e: unknown) => {
				error = errorMessage(e);
			})
			.finally(() => {
				loading = false;
			});
	});

	$effect(() => {
		entryForm.routine_id = selectedRoutineId;
		entryForm.date = selectedDate;
		noteForm.date = selectedDate;
	});

	$effect(() => {
		if (loading) return;
		resetCheckinForm(selectedDate);
		void loadDailySidecars().catch((e: unknown) => {
			error = errorMessage(e);
		});
	});

	$effect(() => {
		if (!selectedRoutineId || loading) return;
		void api.getRoutineEntries(selectedRoutineId, selectedDate)
			.then((response) => {
				entries = response.entries;
			})
			.catch((e: unknown) => {
				error = errorMessage(e);
			});
	});

	let activeCount = $derived.by(() => routines.filter((routine) => routine.status === 'active').length);
	let todaysLogs = $derived.by(() => entries.length);
	let selectedRoutine = $derived.by(
		() => routines.find((routine) => routine.id === selectedRoutineId) ?? null
	);

	function resetRoutineForm() {
		routineForm.id = '';
		routineForm.name = '';
		routineForm.category = 'mindfulness';
		routineForm.status = 'active';
		routineForm.description = '';
		routineForm.default_unit = 'boolean';
		routineForm.target_frequency = '';
		routineForm.default_time_of_day = '';
	}

	async function submitRoutine() {
		saving = true;
		error = null;
		try {
			const payload: RoutineInput = {
				...routineForm,
				id: makeId('routine'),
				description: routineForm.description || null,
				target_frequency: routineForm.target_frequency || null,
				default_time_of_day: routineForm.default_time_of_day || null
			};
			const created = await api.createRoutine(payload);
			routines = [...routines, created];
			selectedRoutineId = created.id;
			resetRoutineForm();
		} catch (e: unknown) {
			error = errorMessage(e);
		} finally {
			saving = false;
		}
	}

	async function submitEntry() {
		if (!selectedRoutineId) return;
		saving = true;
		error = null;
		try {
			const payload: RoutineEntryInput = {
				...entryForm,
				id: makeId('entry'),
				routine_id: selectedRoutineId,
				date: selectedDate,
				timestamp_local: entryForm.timestamp_local || null,
				value_text: entryForm.value_text || null,
				notes: entryForm.notes || null
			};
			const created = await api.createRoutineEntry(selectedRoutineId, payload);
			entries = [...entries, created];
			entryForm.value_numeric = null;
			entryForm.value_text = '';
			entryForm.timestamp_local = '';
			entryForm.notes = '';
		} catch (e: unknown) {
			error = errorMessage(e);
		} finally {
			saving = false;
		}
	}

	async function submitCheckin() {
		saving = true;
		error = null;
		try {
			await api.createCheckin({
				...checkinForm,
				id: `checkin-${selectedDate}`,
				date: selectedDate,
				notes: checkinForm.notes || null
			});
			checkinExists = true;
		} catch (e: unknown) {
			error = errorMessage(e);
		} finally {
			saving = false;
		}
	}

	async function submitNote() {
		saving = true;
		error = null;
		try {
			const created = await api.createNote({
				...noteForm,
				id: makeId('note'),
				date: selectedDate,
				content: noteForm.content.trim(),
				tags: noteForm.tags
			});
			notes = [...notes, created];
			noteForm.title = '';
			noteForm.content = '';
		} catch (e: unknown) {
			error = errorMessage(e);
		} finally {
			saving = false;
		}
	}
</script>

{#if loading}
	<section class="loading-shell">
		<div class="loading-card">Loading routines foundation...</div>
	</section>
{:else}
	<section class="routines-shell">
		<div class="hero-band">
			<div>
				<p class="eyebrow">Phase 1 foundation</p>
				<h1>Build the behavior layer before the assistant starts talking.</h1>
				<p class="hero-copy">
					Track the small interventions that Garmin cannot infer: meditation, mobility, food
					protocols, soreness, and the daily texture that makes the charts make sense.
				</p>
			</div>
			<div class="hero-stats">
				<div class="hero-stat">
					<span>Active routines</span>
					<strong>{activeCount}</strong>
				</div>
				<div class="hero-stat">
					<span>Logs on {selectedDate}</span>
					<strong>{todaysLogs}</strong>
				</div>
				<div class="hero-stat">
					<span>Check-in</span>
					<strong>{checkinExists ? 'Captured' : 'Missing'}</strong>
				</div>
			</div>
		</div>

		{#if error}
			<div class="error-banner">{error}</div>
		{/if}

		<div class="control-row">
			<label class="date-card">
				<span>Context day</span>
				<input type="date" bind:value={selectedDate} />
			</label>
			<div class="selected-routine-card">
				<span>Log against</span>
				<select bind:value={selectedRoutineId}>
					<option value="">Select a routine</option>
					{#each routines as routine}
						<option value={routine.id}>{routine.name}</option>
					{/each}
				</select>
			</div>
		</div>

		<div class="dashboard-grid">
			<section class="panel panel-form">
				<div class="panel-head">
					<p>Create routine</p>
					<h2>Define a repeatable behavior</h2>
				</div>
				<div class="field-grid">
					<label>
						<span>Name</span>
						<input bind:value={routineForm.name} placeholder="Evening meditation" />
					</label>
					<label>
						<span>Category</span>
						<select bind:value={routineForm.category}>
							{#each categoryOptions as option}
								<option value={option}>{option}</option>
							{/each}
						</select>
					</label>
					<label>
						<span>Default unit</span>
						<select bind:value={routineForm.default_unit}>
							{#each unitOptions as option}
								<option value={option}>{option}</option>
							{/each}
						</select>
					</label>
					<label>
						<span>Target frequency</span>
						<input bind:value={routineForm.target_frequency} placeholder="5x / week" />
					</label>
					<label class="wide">
						<span>Description</span>
						<textarea
							bind:value={routineForm.description}
							rows="3"
							placeholder="What exactly counts as a completed session?"
						></textarea>
					</label>
				</div>
				<button class="primary-action" onclick={submitRoutine} disabled={saving || !routineForm.name}>
					Save routine
				</button>
			</section>

			<section class="panel panel-log">
				<div class="panel-head">
					<p>Quick log</p>
					<h2>{selectedRoutine ? selectedRoutine.name : 'Choose a routine to log'}</h2>
				</div>
				{#if selectedRoutine}
					<div class="field-grid">
						<label>
							<span>Completion</span>
							<select bind:value={entryForm.completion_state}>
								<option value="completed">completed</option>
								<option value="partial">partial</option>
								<option value="skipped">skipped</option>
							</select>
						</label>
						<label>
							<span>Numeric value</span>
							<input type="number" bind:value={entryForm.value_numeric} placeholder="10" />
						</label>
						<label>
							<span>Timestamp</span>
							<input type="datetime-local" bind:value={entryForm.timestamp_local} />
						</label>
						<label class="wide">
							<span>Notes</span>
							<textarea bind:value={entryForm.notes} rows="3" placeholder="How did it feel?"></textarea>
						</label>
					</div>
					<button class="primary-action" onclick={submitEntry} disabled={saving}>
						Log for {selectedDate}
					</button>
				{:else}
					<p class="empty-copy">Create a routine first, then use this panel to log adherence.</p>
				{/if}
			</section>

			<section class="panel panel-checkin">
				<div class="panel-head">
					<p>Daily check-in</p>
					<h2>Subjective context</h2>
				</div>
				<div class="slider-grid">
					<label><span>Energy</span><input type="number" min="1" max="5" bind:value={checkinForm.energy} /></label>
					<label><span>Mood</span><input type="number" min="1" max="5" bind:value={checkinForm.mood} /></label>
					<label><span>Motivation</span><input type="number" min="1" max="5" bind:value={checkinForm.motivation} /></label>
					<label><span>Soreness</span><input type="number" min="1" max="5" bind:value={checkinForm.soreness} /></label>
					<label><span>Stress</span><input type="number" min="1" max="5" bind:value={checkinForm.stress_subjective} /></label>
					<label><span>Sleep quality</span><input type="number" min="1" max="5" bind:value={checkinForm.sleep_quality_subjective} /></label>
				</div>
				<label class="wide">
					<span>Notes</span>
					<textarea bind:value={checkinForm.notes} rows="3" placeholder="Travel, soreness, big workday, poor appetite..."></textarea>
				</label>
				<div class="flag-row">
					<label><input type="checkbox" bind:checked={checkinForm.illness_flag} /> illness</label>
					<label><input type="checkbox" bind:checked={checkinForm.travel_flag} /> travel</label>
					<label><input type="checkbox" bind:checked={checkinForm.alcohol_flag} /> alcohol</label>
				</div>
				<button class="secondary-action" onclick={submitCheckin} disabled={saving}>
					Save check-in
				</button>
			</section>

			<section class="panel panel-note">
				<div class="panel-head">
					<p>Context notes</p>
					<h2>Capture the story around the numbers</h2>
				</div>
				<label>
					<span>Title</span>
					<input bind:value={noteForm.title} placeholder="Late dinner after lifting" />
				</label>
				<label>
					<span>Category</span>
					<input bind:value={noteForm.category} placeholder="nutrition" />
				</label>
				<label class="wide">
					<span>Note</span>
					<textarea bind:value={noteForm.content} rows="4" placeholder="What changed today that future analysis should know?"></textarea>
				</label>
				<button class="secondary-action" onclick={submitNote} disabled={saving || !noteForm.title || !noteForm.content}>
					Add note
				</button>
			</section>
		</div>

		<div class="library-grid">
			<section class="panel library-panel">
				<div class="panel-head">
					<p>Routine library</p>
					<h2>{routines.length === 0 ? 'No routines yet' : `${routines.length} tracked behaviors`}</h2>
				</div>
				<div class="routine-list">
					{#each routines as routine}
						<button
							class:selected={routine.id === selectedRoutineId}
							class="routine-card"
							onclick={() => { selectedRoutineId = routine.id; }}
						>
							<div class="routine-card-head">
								<strong>{routine.name}</strong>
								<span style={`color:${categoryAccent[routine.category] ?? categoryAccent.custom}`}>{routine.category}</span>
							</div>
							<p>{routine.description || 'No description yet.'}</p>
							<div class="routine-meta">
								<span>{routine.default_unit}</span>
								<span>{routine.target_frequency || 'open cadence'}</span>
							</div>
						</button>
					{/each}
				</div>
			</section>

			<section class="panel activity-panel">
				<div class="panel-head">
					<p>{selectedDate}</p>
					<h2>Logged activity + notes</h2>
				</div>
				<div class="stack-list">
					{#if entries.length === 0}
						<div class="empty-card">No routine logs for this day yet.</div>
					{:else}
						{#each entries as entry}
							<div class="stack-card">
								<div class="stack-card-head">
									<strong>{selectedRoutine?.name || entry.routine_id}</strong>
									<span>{entry.completion_state}</span>
								</div>
								<p>{entry.notes || 'No note attached.'}</p>
							</div>
						{/each}
					{/if}

					{#if notes.length === 0}
						<div class="empty-card">No context notes for this day yet.</div>
					{:else}
						{#each notes as note}
							<div class="stack-card note-card">
								<div class="stack-card-head">
									<strong>{note.title}</strong>
									<span>{note.category}</span>
								</div>
								<p>{note.content}</p>
							</div>
						{/each}
					{/if}
				</div>
			</section>
		</div>
	</section>
{/if}

<style>
	.routines-shell {
		display: grid;
		gap: 22px;
	}

	.loading-shell {
		padding: 48px 0;
	}

	.loading-card,
	.error-banner,
	.panel,
	.date-card,
	.selected-routine-card {
		border: 1px solid rgba(255, 255, 255, 0.08);
		background:
			linear-gradient(135deg, rgba(14, 23, 36, 0.95), rgba(8, 14, 25, 0.92)),
			radial-gradient(circle at top left, rgba(91, 181, 166, 0.14), transparent 40%);
		border-radius: 20px;
		box-shadow: 0 24px 60px rgba(0, 0, 0, 0.24);
	}

	.hero-band {
		display: grid;
		grid-template-columns: minmax(0, 1.4fr) minmax(280px, 0.8fr);
		gap: 18px;
		padding: 28px;
		border-radius: 26px;
		border: 1px solid rgba(255, 255, 255, 0.08);
		background:
			radial-gradient(circle at top right, rgba(99, 102, 176, 0.18), transparent 35%),
			radial-gradient(circle at bottom left, rgba(91, 181, 166, 0.2), transparent 32%),
			linear-gradient(140deg, rgba(11, 19, 31, 0.96), rgba(15, 23, 35, 0.9));
	}

	.eyebrow,
	.panel-head p {
		margin: 0 0 8px;
		font-family: 'DM Mono', monospace;
		font-size: 11px;
		letter-spacing: 0.18em;
		text-transform: uppercase;
		color: #7ea8a0;
	}

	h1,
	h2 {
		margin: 0;
		color: #f3f7fb;
	}

	h1 {
		font-size: clamp(2rem, 5vw, 3.4rem);
		line-height: 0.95;
		max-width: 12ch;
	}

	.hero-copy {
		max-width: 62ch;
		margin: 16px 0 0;
		color: #9bb0bf;
		line-height: 1.6;
	}

	.hero-stats,
	.dashboard-grid,
	.library-grid,
	.control-row,
	.field-grid,
	.slider-grid,
	.flag-row,
	.routine-meta,
	.stack-card-head,
	.routine-card-head {
		display: grid;
	}

	.hero-stats {
		grid-template-columns: 1fr;
		gap: 12px;
	}

	.hero-stat {
		padding: 16px 18px;
		border-radius: 18px;
		background: rgba(255, 255, 255, 0.04);
	}

	.hero-stat span,
	.stack-card-head span,
	.routine-card-head span,
	.routine-meta span {
		font-family: 'DM Mono', monospace;
		font-size: 11px;
		letter-spacing: 0.08em;
		text-transform: uppercase;
		color: #8da0af;
	}

	.hero-stat strong {
		display: block;
		margin-top: 8px;
		font-size: 1.75rem;
		color: #f8fbff;
	}

	.error-banner {
		padding: 14px 16px;
		color: #ffd4cf;
	}

	.control-row {
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: 14px;
	}

	.date-card,
	.selected-routine-card,
	.panel {
		padding: 20px;
	}

	.date-card span,
	.selected-routine-card span,
	label span {
		display: block;
		margin-bottom: 8px;
		font-family: 'DM Mono', monospace;
		font-size: 11px;
		letter-spacing: 0.08em;
		text-transform: uppercase;
		color: #8da0af;
	}

	.dashboard-grid {
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: 18px;
	}

	.library-grid {
		grid-template-columns: 1.1fr 0.9fr;
		gap: 18px;
	}

	.field-grid,
	.slider-grid {
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: 14px;
	}

	.wide {
		grid-column: 1 / -1;
	}

	input,
	select,
	textarea,
	button {
		font: inherit;
	}

	input,
	select,
	textarea {
		width: 100%;
		border: 1px solid rgba(255, 255, 255, 0.08);
		background: rgba(255, 255, 255, 0.04);
		color: #f2f7fb;
		border-radius: 14px;
		padding: 12px 14px;
		box-sizing: border-box;
	}

	textarea {
		resize: vertical;
		min-height: 92px;
	}

	.primary-action,
	.secondary-action {
		margin-top: 16px;
		border: 0;
		border-radius: 999px;
		padding: 12px 18px;
		cursor: pointer;
		font-weight: 600;
	}

	.primary-action {
		background: linear-gradient(90deg, #5bb5a6, #74d4c3);
		color: #08131f;
	}

	.secondary-action {
		background: linear-gradient(90deg, rgba(99, 102, 176, 0.95), rgba(139, 141, 214, 0.95));
		color: #f6f8fb;
	}

	button:disabled {
		opacity: 0.55;
		cursor: not-allowed;
	}

	.flag-row {
		grid-template-columns: repeat(3, minmax(0, 1fr));
		gap: 10px;
		margin-top: 12px;
	}

	.flag-row label {
		display: flex;
		align-items: center;
		gap: 8px;
		padding: 10px 12px;
		border-radius: 14px;
		background: rgba(255, 255, 255, 0.04);
		color: #d7e2eb;
	}

	.routine-list,
	.stack-list {
		display: grid;
		gap: 12px;
	}

	.routine-card,
	.stack-card,
	.empty-card {
		width: 100%;
		padding: 16px;
		border-radius: 18px;
		border: 1px solid rgba(255, 255, 255, 0.08);
		background: rgba(255, 255, 255, 0.035);
		text-align: left;
	}

	.routine-card {
		cursor: pointer;
	}

	.routine-card.selected {
		border-color: rgba(91, 181, 166, 0.42);
		box-shadow: inset 0 0 0 1px rgba(91, 181, 166, 0.25);
	}

	.routine-card-head,
	.stack-card-head {
		grid-template-columns: minmax(0, 1fr) auto;
		align-items: start;
		gap: 10px;
	}

	.routine-card p,
	.stack-card p,
	.empty-copy,
	.empty-card {
		margin: 10px 0 0;
		color: #97abba;
		line-height: 1.5;
	}

	.routine-meta {
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: 8px;
		margin-top: 12px;
	}

	.note-card {
		background: linear-gradient(135deg, rgba(99, 102, 176, 0.12), rgba(255, 255, 255, 0.03));
	}

	@media (max-width: 980px) {
		.hero-band,
		.dashboard-grid,
		.library-grid,
		.control-row,
		.field-grid,
		.slider-grid,
		.flag-row {
			grid-template-columns: 1fr;
		}

		h1 {
			max-width: none;
		}
	}
</style>
