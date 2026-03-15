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

	const categoryAccent: Record<string, string> = {
		mindfulness: COLORS.hrv,
		nutrition: COLORS.skinTemp,
		strength: COLORS.heartRate,
		mobility: COLORS.respiration,
		sleep: COLORS.sleep,
		recovery: COLORS.bodyBattery,
		core: COLORS.stress,
		supporting: COLORS.spo2,
		custom: '#8a9baa'
	};

	const categoryLabel: Record<string, string> = {
		mindfulness: 'Mindfulness',
		mobility: 'Morning Stretch',
		core: 'Core Rotation',
		supporting: 'Supporting Work',
		recovery: 'Recovery',
		strength: 'Strength',
		nutrition: 'Nutrition',
		sleep: 'Sleep',
		custom: 'Custom'
	};

	const categoryOrder = [
		'mindfulness',
		'mobility',
		'core',
		'supporting',
		'recovery',
		'strength',
		'nutrition',
		'sleep',
		'custom'
	];

	let loading = $state(true);
	let saving = $state(false);
	let error: string | null = $state(null);

	let selectedDate = $state(new Date().toISOString().slice(0, 10));
	let routines: Routine[] = $state([]);
	let todayEntries: RoutineEntry[] = $state([]);
	let notes: Note[] = $state([]);
	let checkinExists = $state(false);

	let filterCategory = $state('all');
	let searchQuery = $state('');
	let expandedRoutineId = $state<string | null>(null);
	let showCheckin = $state(false);
	let showNotes = $state(false);
	let showCreateForm = $state(false);

	let sidecarRequestToken = 0;
	let entriesRequestToken = 0;

	// Inline log form state
	let logNumeric = $state<number | null>(null);
	let logNotes = $state('');
	let logCompletion = $state<string>('completed');

	// Check-in form
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

	// Note form
	let noteForm = $state<Required<NoteInput>>({
		id: '',
		date: '',
		category: 'reflection',
		title: '',
		content: '',
		tags: []
	});

	// Create routine form
	let routineForm = $state({
		name: '',
		category: 'mindfulness',
		description: '',
		default_unit: 'boolean',
		target_frequency: ''
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

	// Grouped routines by category
	let categories = $derived.by(() => {
		const cats = new Set(routines.map((r) => r.category));
		return categoryOrder.filter((c) => cats.has(c));
	});

	let filteredRoutines = $derived.by(() => {
		let filtered = routines.filter((r) => r.status === 'active');
		if (filterCategory !== 'all') {
			filtered = filtered.filter((r) => r.category === filterCategory);
		}
		if (searchQuery.trim()) {
			const q = searchQuery.toLowerCase();
			filtered = filtered.filter(
				(r) =>
					r.name.toLowerCase().includes(q) ||
					(r.description ?? '').toLowerCase().includes(q)
			);
		}
		return filtered;
	});

	let groupedRoutines = $derived.by(() => {
		const groups: Record<string, Routine[]> = {};
		for (const r of filteredRoutines) {
			if (!groups[r.category]) groups[r.category] = [];
			groups[r.category].push(r);
		}
		return groups;
	});

	// Set of routine IDs that have entries today
	let loggedRoutineIds = $derived.by(() => new Set(todayEntries.map((e) => e.routine_id)));

	let activeCount = $derived.by(() => routines.filter((r) => r.status === 'active').length);
	let todayLogCount = $derived.by(() => todayEntries.length);

	async function loadPageData() {
		error = null;
		const [daysResponse, routinesResponse] = await Promise.all([
			api.getDays(),
			api.getRoutines()
		]);
		const latestDay = daysResponse.days[daysResponse.days.length - 1];
		if (latestDay) selectedDate = latestDay;
		routines = routinesResponse.routines;
	}

	async function loadDailySidecars(date: string, requestToken: number) {
		const [notesResponse, checkinsResponse] = await Promise.all([
			api.getNotes(date),
			api.getCheckins(date)
		]);
		if (requestToken !== sidecarRequestToken || date !== selectedDate) return;
		notes = notesResponse.notes;
		const existingCheckin = checkinsResponse.checkins[0] ?? null;
		checkinExists = existingCheckin !== null;
		applyCheckinForm(existingCheckin, date);
	}

	async function loadTodayEntries(date: string, requestToken: number) {
		const response = await api.getRoutineEntriesByDate(date);
		if (requestToken !== entriesRequestToken || date !== selectedDate) return;
		todayEntries = response.entries;
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
		if (loading) return;
		const date = selectedDate;
		sidecarRequestToken += 1;
		const requestToken = sidecarRequestToken;
		notes = [];
		checkinExists = false;
		resetCheckinForm(date);
		noteForm.date = date;
		void loadDailySidecars(date, requestToken).catch((e: unknown) => {
			error = errorMessage(e);
		});
	});

	$effect(() => {
		if (loading) return;
		const date = selectedDate;
		entriesRequestToken += 1;
		const requestToken = entriesRequestToken;
		todayEntries = [];
		void loadTodayEntries(date, requestToken).catch((e: unknown) => {
			error = errorMessage(e);
		});
	});

	async function quickLog(routine: Routine) {
		saving = true;
		error = null;
		try {
			const payload: RoutineEntryInput = {
				id: makeId('entry'),
				routine_id: routine.id,
				date: selectedDate,
				timestamp_local: null,
				value_numeric: null,
				value_text: null,
				completion_state: 'completed',
				source: 'manual',
				notes: null
			};
			const created = await api.createRoutineEntry(routine.id, payload);
			todayEntries = [...todayEntries, created];
		} catch (e: unknown) {
			error = errorMessage(e);
		} finally {
			saving = false;
		}
	}

	async function detailLog(routine: Routine) {
		saving = true;
		error = null;
		try {
			const payload: RoutineEntryInput = {
				id: makeId('entry'),
				routine_id: routine.id,
				date: selectedDate,
				timestamp_local: null,
				value_numeric: logNumeric,
				value_text: null,
				completion_state: logCompletion,
				source: 'manual',
				notes: logNotes.trim() || null
			};
			const created = await api.createRoutineEntry(routine.id, payload);
			todayEntries = [...todayEntries, created];
			expandedRoutineId = null;
			logNumeric = null;
			logNotes = '';
			logCompletion = 'completed';
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

	async function submitRoutine() {
		saving = true;
		error = null;
		try {
			const payload: RoutineInput = {
				id: makeId('routine'),
				name: routineForm.name,
				category: routineForm.category,
				status: 'active',
				description: routineForm.description || null,
				default_unit: routineForm.default_unit,
				target_frequency: routineForm.target_frequency || null,
				default_time_of_day: null,
				tags: [],
				linked_goal_ids: []
			};
			const created = await api.createRoutine(payload);
			routines = [...routines, created];
			showCreateForm = false;
			routineForm.name = '';
			routineForm.description = '';
			routineForm.target_frequency = '';
		} catch (e: unknown) {
			error = errorMessage(e);
		} finally {
			saving = false;
		}
	}

	function toggleExpand(routineId: string) {
		if (expandedRoutineId === routineId) {
			expandedRoutineId = null;
		} else {
			expandedRoutineId = routineId;
			logNumeric = null;
			logNotes = '';
			logCompletion = 'completed';
		}
	}
</script>

<svelte:head>
	<title>Routines - Garmin Stats</title>
</svelte:head>

{#if loading}
	<section class="loading-shell">
		<div class="loading-card">Loading routines...</div>
	</section>
{:else}
	<section class="routines-shell">
		{#if error}
			<div class="error-banner">{error}</div>
		{/if}

		<!-- Top bar: date + stats -->
		<div class="top-bar">
			<label class="date-picker">
				<span>Date</span>
				<input type="date" bind:value={selectedDate} />
			</label>
			<div class="stat-chip">
				<span class="stat-label">Routines</span>
				<span class="stat-value">{activeCount}</span>
			</div>
			<div class="stat-chip">
				<span class="stat-label">Logged today</span>
				<span class="stat-value">{todayLogCount}</span>
			</div>
			<div class="stat-chip">
				<span class="stat-label">Check-in</span>
				<span class="stat-value" class:missing={!checkinExists}
					>{checkinExists ? 'Done' : 'Missing'}</span
				>
			</div>
			<button
				class="add-btn"
				onclick={() => {
					showCreateForm = !showCreateForm;
				}}
			>
				{showCreateForm ? 'Cancel' : '+ New'}
			</button>
		</div>

		<!-- Create routine (collapsible) -->
		{#if showCreateForm}
			<div class="create-panel">
				<div class="create-grid">
					<label>
						<span>Name</span>
						<input bind:value={routineForm.name} placeholder="e.g. Evening Wind-Down" />
					</label>
					<label>
						<span>Category</span>
						<select bind:value={routineForm.category}>
							{#each categoryOrder as cat}
								<option value={cat}>{categoryLabel[cat] ?? cat}</option>
							{/each}
						</select>
					</label>
					<label>
						<span>Unit</span>
						<select bind:value={routineForm.default_unit}>
							{#each ['boolean', 'minutes', 'sets', 'reps', 'seconds', 'grams', 'rating'] as u}
								<option value={u}>{u}</option>
							{/each}
						</select>
					</label>
					<label>
						<span>Frequency</span>
						<input bind:value={routineForm.target_frequency} placeholder="5x / week" />
					</label>
				</div>
				<label class="wide-label">
					<span>Description</span>
					<textarea
						bind:value={routineForm.description}
						rows="2"
						placeholder="What counts as done?"
					></textarea>
				</label>
				<button
					class="save-btn"
					onclick={submitRoutine}
					disabled={saving || !routineForm.name}
				>
					Save routine
				</button>
			</div>
		{/if}

		<!-- Category filter + search -->
		<div class="filter-bar">
			<div class="category-tabs">
				<button
					class="cat-tab"
					class:active={filterCategory === 'all'}
					onclick={() => (filterCategory = 'all')}>All</button
				>
				{#each categories as cat}
					<button
						class="cat-tab"
						class:active={filterCategory === cat}
						onclick={() => (filterCategory = cat)}
						style="--accent: {categoryAccent[cat] ?? '#8a9baa'}"
					>
						{categoryLabel[cat] ?? cat}
					</button>
				{/each}
			</div>
			<input
				class="search-input"
				type="text"
				bind:value={searchQuery}
				placeholder="Search..."
			/>
		</div>

		<!-- Routine groups -->
		<div class="routine-groups">
			{#each categoryOrder as cat}
				{#if groupedRoutines[cat]}
					<div class="group">
						<div class="group-header">
							<div
								class="group-color"
								style="background: {categoryAccent[cat] ?? '#8a9baa'}"
							></div>
							<h2 class="group-name">{categoryLabel[cat] ?? cat}</h2>
							<span class="group-count">{groupedRoutines[cat].length} techniques</span>
						</div>
						<div class="technique-list">
							{#each groupedRoutines[cat] as routine (routine.id)}
								{@const isLogged = loggedRoutineIds.has(routine.id)}
								{@const isExpanded = expandedRoutineId === routine.id}
								<div
									class="technique-card"
									class:logged={isLogged}
									class:expanded={isExpanded}
								>
									<div class="technique-row">
										<button
											class="technique-info"
											onclick={() => toggleExpand(routine.id)}
										>
											<span class="technique-name">{routine.name}</span>
											{#if routine.description}
												<span class="technique-desc">{routine.description}</span>
											{/if}
										</button>
										<div class="technique-actions">
											{#if isLogged}
												<span class="logged-badge">Logged</span>
											{:else}
												<button
													class="quick-log-btn"
													onclick={() => quickLog(routine)}
													disabled={saving}
													title="Mark as done"
												>
													Done
												</button>
											{/if}
										</div>
									</div>

									{#if isExpanded}
										<div class="expand-panel">
											<div class="expand-fields">
												<label>
													<span>Completion</span>
													<select bind:value={logCompletion}>
														<option value="completed">Completed</option>
														<option value="partial">Partial</option>
														<option value="skipped">Skipped</option>
													</select>
												</label>
												<label>
													<span>Value ({routine.default_unit})</span>
													<input
														type="number"
														bind:value={logNumeric}
														placeholder="—"
													/>
												</label>
											</div>
											<label class="wide-label">
												<span>Notes</span>
												<textarea
													bind:value={logNotes}
													rows="2"
													placeholder="How did it feel?"
												></textarea>
											</label>
											<button
												class="log-detail-btn"
												onclick={() => detailLog(routine)}
												disabled={saving}
											>
												Log with details
											</button>
										</div>
									{/if}
								</div>
							{/each}
						</div>
					</div>
				{/if}
			{/each}

			{#if Object.keys(groupedRoutines).length === 0}
				<p class="empty-msg">No routines match your filters.</p>
			{/if}
		</div>

		<!-- Collapsible: Daily check-in -->
		<button
			class="section-toggle"
			onclick={() => {
				showCheckin = !showCheckin;
			}}
		>
			<span>Daily check-in</span>
			<span class="toggle-badge" class:done={checkinExists}
				>{checkinExists ? 'Captured' : 'Missing'}</span
			>
			<span class="toggle-arrow">{showCheckin ? '\u25B2' : '\u25BC'}</span>
		</button>
		{#if showCheckin}
			<div class="collapsible-panel">
				<div class="checkin-grid">
					<label
						><span>Energy</span><input
							type="number"
							min="1"
							max="5"
							bind:value={checkinForm.energy}
							placeholder="1-5"
						/></label
					>
					<label
						><span>Mood</span><input
							type="number"
							min="1"
							max="5"
							bind:value={checkinForm.mood}
							placeholder="1-5"
						/></label
					>
					<label
						><span>Motivation</span><input
							type="number"
							min="1"
							max="5"
							bind:value={checkinForm.motivation}
							placeholder="1-5"
						/></label
					>
					<label
						><span>Soreness</span><input
							type="number"
							min="1"
							max="5"
							bind:value={checkinForm.soreness}
							placeholder="1-5"
						/></label
					>
					<label
						><span>Stress</span><input
							type="number"
							min="1"
							max="5"
							bind:value={checkinForm.stress_subjective}
							placeholder="1-5"
						/></label
					>
					<label
						><span>Sleep quality</span><input
							type="number"
							min="1"
							max="5"
							bind:value={checkinForm.sleep_quality_subjective}
							placeholder="1-5"
						/></label
					>
				</div>
				<label class="wide-label">
					<span>Notes</span>
					<textarea
						bind:value={checkinForm.notes}
						rows="2"
						placeholder="Context: travel, soreness, big workday..."
					></textarea>
				</label>
				<div class="flag-row">
					<label class="flag"
						><input type="checkbox" bind:checked={checkinForm.illness_flag} /> illness</label
					>
					<label class="flag"
						><input type="checkbox" bind:checked={checkinForm.travel_flag} /> travel</label
					>
					<label class="flag"
						><input type="checkbox" bind:checked={checkinForm.alcohol_flag} /> alcohol</label
					>
				</div>
				<button class="save-btn secondary" onclick={submitCheckin} disabled={saving}
					>Save check-in</button
				>
			</div>
		{/if}

		<!-- Collapsible: Notes -->
		<button
			class="section-toggle"
			onclick={() => {
				showNotes = !showNotes;
			}}
		>
			<span>Context notes</span>
			<span class="toggle-badge">{notes.length}</span>
			<span class="toggle-arrow">{showNotes ? '\u25B2' : '\u25BC'}</span>
		</button>
		{#if showNotes}
			<div class="collapsible-panel">
				{#if notes.length > 0}
					<div class="notes-list">
						{#each notes as note}
							<div class="note-card">
								<strong>{note.title}</strong>
								<span class="note-cat">{note.category}</span>
								<p>{note.content}</p>
							</div>
						{/each}
					</div>
				{/if}
				<div class="note-form">
					<div class="note-form-row">
						<label
							><span>Title</span><input
								bind:value={noteForm.title}
								placeholder="Late dinner after lifting"
							/></label
						>
						<label
							><span>Category</span><input
								bind:value={noteForm.category}
								placeholder="reflection"
							/></label
						>
					</div>
					<label class="wide-label">
						<span>Note</span>
						<textarea
							bind:value={noteForm.content}
							rows="2"
							placeholder="What changed today?"
						></textarea>
					</label>
					<button
						class="save-btn secondary"
						onclick={submitNote}
						disabled={saving || !noteForm.title || !noteForm.content}>Add note</button
					>
				</div>
			</div>
		{/if}
	</section>
{/if}

<style>
	.routines-shell {
		display: flex;
		flex-direction: column;
		gap: 12px;
	}

	.loading-shell {
		padding: 48px 0;
	}
	.loading-card {
		text-align: center;
		color: #5e7282;
		font-family: 'DM Mono', monospace;
		font-size: 12px;
	}

	.error-banner {
		padding: 10px 14px;
		border-radius: 6px;
		background: rgba(224, 107, 107, 0.1);
		border: 1px solid rgba(224, 107, 107, 0.2);
		color: #ffd4cf;
		font-size: 13px;
	}

	/* Top bar */
	.top-bar {
		display: flex;
		align-items: flex-end;
		gap: 12px;
		flex-wrap: wrap;
	}

	.date-picker {
		display: flex;
		flex-direction: column;
		gap: 4px;
	}

	.date-picker span,
	.stat-label {
		font-family: 'DM Mono', monospace;
		font-size: 10px;
		letter-spacing: 0.08em;
		text-transform: uppercase;
		color: #5e7282;
	}

	.date-picker input {
		border: 1px solid rgba(255, 255, 255, 0.08);
		background: rgba(255, 255, 255, 0.04);
		color: #f2f7fb;
		border-radius: 6px;
		padding: 6px 10px;
		font: inherit;
		font-size: 13px;
	}

	.stat-chip {
		display: flex;
		flex-direction: column;
		gap: 2px;
		padding: 6px 14px;
		border-radius: 6px;
		background: rgba(255, 255, 255, 0.03);
		border: 1px solid rgba(255, 255, 255, 0.06);
	}

	.stat-value {
		font-family: 'Instrument Sans', sans-serif;
		font-size: 16px;
		font-weight: 600;
		color: #e8f0f5;
	}

	.stat-value.missing {
		color: #e06b6b;
	}

	.add-btn {
		margin-left: auto;
		font-family: 'DM Mono', monospace;
		font-size: 11px;
		padding: 6px 14px;
		border-radius: 6px;
		border: 1px solid rgba(91, 181, 166, 0.3);
		background: rgba(91, 181, 166, 0.08);
		color: #5bb5a6;
		cursor: pointer;
		transition: all 0.2s;
	}

	.add-btn:hover {
		background: rgba(91, 181, 166, 0.15);
	}

	/* Create form */
	.create-panel {
		padding: 16px;
		border-radius: 8px;
		background: rgba(255, 255, 255, 0.02);
		border: 1px solid rgba(255, 255, 255, 0.06);
		display: flex;
		flex-direction: column;
		gap: 10px;
	}

	.create-grid {
		display: grid;
		grid-template-columns: repeat(4, 1fr);
		gap: 10px;
	}

	/* Filter bar */
	.filter-bar {
		display: flex;
		align-items: center;
		gap: 10px;
		flex-wrap: wrap;
	}

	.category-tabs {
		display: flex;
		gap: 2px;
		flex-wrap: wrap;
	}

	.cat-tab {
		font-family: 'DM Mono', monospace;
		font-size: 11px;
		padding: 4px 10px;
		border-radius: 4px;
		border: none;
		background: transparent;
		color: #4a5e6d;
		cursor: pointer;
		transition: all 0.15s;
	}

	.cat-tab:hover {
		color: #8fa3b0;
	}
	.cat-tab.active {
		color: var(--accent, #5bb5a6);
		background: color-mix(in srgb, var(--accent, #5bb5a6) 10%, transparent);
	}

	.search-input {
		margin-left: auto;
		border: 1px solid rgba(255, 255, 255, 0.08);
		background: rgba(255, 255, 255, 0.04);
		color: #f2f7fb;
		border-radius: 6px;
		padding: 5px 10px;
		font: inherit;
		font-size: 12px;
		width: 160px;
	}

	.search-input::placeholder {
		color: #3a4e5d;
	}

	/* Routine groups */
	.routine-groups {
		display: flex;
		flex-direction: column;
		gap: 16px;
	}

	.group {
		display: flex;
		flex-direction: column;
		gap: 6px;
	}

	.group-header {
		display: flex;
		align-items: center;
		gap: 8px;
		padding: 4px 0;
	}

	.group-color {
		width: 3px;
		height: 16px;
		border-radius: 2px;
	}

	.group-name {
		font-family: 'Instrument Sans', sans-serif;
		font-size: 14px;
		font-weight: 600;
		color: #c8d6e0;
		margin: 0;
	}

	.group-count {
		font-family: 'DM Mono', monospace;
		font-size: 10px;
		color: #4a5e6d;
		margin-left: 4px;
	}

	.technique-list {
		display: flex;
		flex-direction: column;
		gap: 2px;
	}

	.technique-card {
		border-radius: 6px;
		border: 1px solid rgba(255, 255, 255, 0.05);
		background: rgba(255, 255, 255, 0.02);
		transition: all 0.15s;
	}

	.technique-card:hover {
		border-color: rgba(255, 255, 255, 0.1);
	}
	.technique-card.logged {
		border-color: rgba(91, 181, 166, 0.2);
		background: rgba(91, 181, 166, 0.03);
	}
	.technique-card.expanded {
		border-color: rgba(255, 255, 255, 0.12);
	}

	.technique-row {
		display: flex;
		align-items: center;
		gap: 8px;
		padding: 8px 12px;
	}

	.technique-info {
		flex: 1;
		display: flex;
		flex-direction: column;
		gap: 2px;
		background: none;
		border: none;
		cursor: pointer;
		text-align: left;
		color: inherit;
		padding: 0;
	}

	.technique-name {
		font-family: 'Instrument Sans', sans-serif;
		font-size: 13px;
		font-weight: 500;
		color: #e0eaf0;
	}

	.technique-desc {
		font-family: 'DM Mono', monospace;
		font-size: 10px;
		color: #5e7282;
		line-height: 1.3;
		max-width: 600px;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.technique-actions {
		flex-shrink: 0;
	}

	.logged-badge {
		font-family: 'DM Mono', monospace;
		font-size: 10px;
		color: #5bb5a6;
		padding: 3px 8px;
		border-radius: 4px;
		background: rgba(91, 181, 166, 0.1);
	}

	.quick-log-btn {
		font-family: 'DM Mono', monospace;
		font-size: 11px;
		padding: 4px 12px;
		border-radius: 4px;
		border: 1px solid rgba(91, 181, 166, 0.3);
		background: rgba(91, 181, 166, 0.08);
		color: #5bb5a6;
		cursor: pointer;
		transition: all 0.15s;
	}

	.quick-log-btn:hover {
		background: rgba(91, 181, 166, 0.2);
	}
	.quick-log-btn:disabled {
		opacity: 0.4;
		cursor: not-allowed;
	}

	/* Expand panel (detail log) */
	.expand-panel {
		padding: 8px 12px 12px;
		border-top: 1px solid rgba(255, 255, 255, 0.04);
		display: flex;
		flex-direction: column;
		gap: 8px;
	}

	.expand-fields {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 8px;
	}

	.log-detail-btn {
		align-self: flex-end;
		font-family: 'DM Mono', monospace;
		font-size: 11px;
		padding: 5px 14px;
		border-radius: 6px;
		border: none;
		background: #5bb5a6;
		color: #0d1520;
		font-weight: 500;
		cursor: pointer;
		transition: all 0.2s;
	}

	.log-detail-btn:disabled {
		opacity: 0.4;
		cursor: not-allowed;
	}
	.log-detail-btn:hover:not(:disabled) {
		background: #6dc7b8;
	}

	/* Section toggles (check-in, notes) */
	.section-toggle {
		display: flex;
		align-items: center;
		gap: 8px;
		width: 100%;
		padding: 10px 14px;
		border-radius: 6px;
		border: 1px solid rgba(255, 255, 255, 0.06);
		background: rgba(255, 255, 255, 0.02);
		color: #c8d6e0;
		font-family: 'Instrument Sans', sans-serif;
		font-size: 13px;
		font-weight: 500;
		cursor: pointer;
		transition: all 0.15s;
		text-align: left;
	}

	.section-toggle:hover {
		border-color: rgba(255, 255, 255, 0.1);
	}

	.toggle-badge {
		font-family: 'DM Mono', monospace;
		font-size: 10px;
		padding: 2px 8px;
		border-radius: 4px;
		background: rgba(224, 107, 107, 0.1);
		color: #e06b6b;
	}

	.toggle-badge.done {
		background: rgba(91, 181, 166, 0.1);
		color: #5bb5a6;
	}

	.toggle-arrow {
		margin-left: auto;
		font-size: 10px;
		color: #4a5e6d;
	}

	/* Collapsible panels */
	.collapsible-panel {
		padding: 14px;
		border-radius: 8px;
		background: rgba(255, 255, 255, 0.02);
		border: 1px solid rgba(255, 255, 255, 0.06);
		display: flex;
		flex-direction: column;
		gap: 10px;
	}

	.checkin-grid {
		display: grid;
		grid-template-columns: repeat(3, 1fr);
		gap: 8px;
	}

	.flag-row {
		display: flex;
		gap: 10px;
	}

	.flag {
		display: flex;
		align-items: center;
		gap: 6px;
		font-size: 12px;
		color: #8da0af;
	}

	.flag input[type='checkbox'] {
		width: auto;
		margin: 0;
	}

	/* Notes */
	.notes-list {
		display: flex;
		flex-direction: column;
		gap: 6px;
	}

	.note-card {
		padding: 8px 12px;
		border-radius: 6px;
		background: rgba(99, 102, 176, 0.08);
		border: 1px solid rgba(99, 102, 176, 0.15);
	}

	.note-card strong {
		color: #c8d6e0;
		font-size: 13px;
	}

	.note-cat {
		font-family: 'DM Mono', monospace;
		font-size: 10px;
		color: #6366b0;
		margin-left: 8px;
	}

	.note-card p {
		margin: 4px 0 0;
		color: #8da0af;
		font-size: 12px;
		line-height: 1.4;
	}

	.note-form {
		display: flex;
		flex-direction: column;
		gap: 8px;
	}

	.note-form-row {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 8px;
	}

	/* Shared form elements */
	label span {
		display: block;
		margin-bottom: 3px;
		font-family: 'DM Mono', monospace;
		font-size: 10px;
		letter-spacing: 0.08em;
		text-transform: uppercase;
		color: #5e7282;
	}

	input,
	select,
	textarea {
		width: 100%;
		border: 1px solid rgba(255, 255, 255, 0.08);
		background: rgba(255, 255, 255, 0.04);
		color: #f2f7fb;
		border-radius: 6px;
		padding: 6px 10px;
		box-sizing: border-box;
		font: inherit;
		font-size: 13px;
	}

	textarea {
		resize: vertical;
		min-height: 48px;
	}

	.wide-label {
		grid-column: 1 / -1;
	}

	.save-btn {
		align-self: flex-start;
		font-family: 'DM Mono', monospace;
		font-size: 11px;
		padding: 6px 16px;
		border-radius: 6px;
		border: none;
		background: #5bb5a6;
		color: #0d1520;
		font-weight: 500;
		cursor: pointer;
		transition: all 0.2s;
	}

	.save-btn.secondary {
		background: rgba(99, 102, 176, 0.85);
		color: #f6f8fb;
	}

	.save-btn:disabled {
		opacity: 0.4;
		cursor: not-allowed;
	}
	.save-btn:hover:not(:disabled) {
		filter: brightness(1.1);
	}

	.empty-msg {
		text-align: center;
		color: #4a5e6d;
		font-family: 'DM Mono', monospace;
		font-size: 12px;
		padding: 24px 0;
	}

	@media (max-width: 768px) {
		.top-bar {
			flex-direction: column;
			align-items: stretch;
		}
		.add-btn {
			margin-left: 0;
		}
		.create-grid {
			grid-template-columns: 1fr 1fr;
		}
		.checkin-grid {
			grid-template-columns: 1fr 1fr;
		}
		.expand-fields {
			grid-template-columns: 1fr;
		}
		.search-input {
			margin-left: 0;
			width: 100%;
		}
	}
</style>
