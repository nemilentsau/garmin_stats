<script lang="ts">
	import { onMount } from 'svelte';

	import {
		api,
		type RoutineSchedule,
		type ScheduleOccurrence,
		type ScheduleWindow
	} from '$lib/api';
	import { COLORS, withAlpha } from '$lib/colors';
	import { isIsoDateString, localDateIso } from '$lib/date';
	import { errorMessage } from '$lib/utils';

	type LensMode = 'day' | 'routine';
	type SlotName = ScheduleOccurrence['slot'];
	type SlotSection = {
		slot: SlotName;
		label: string;
		color: string;
		shadow: string;
		items: ScheduleOccurrence[];
	};

	const SLOT_ORDER: SlotName[] = ['morning', 'midday', 'evening', 'anytime'];
	const SLOT_LABELS: Record<SlotName, string> = {
		morning: 'Morning',
		midday: 'Midday',
		evening: 'Evening',
		anytime: 'Anytime'
	};
	const SLOT_ACCENTS: Record<SlotName, { color: string; shadow: string }> = {
		morning: { color: COLORS.skinTemp, shadow: withAlpha(COLORS.skinTemp, '26') },
		midday: { color: COLORS.stress, shadow: withAlpha(COLORS.stress, '26') },
		evening: { color: COLORS.hrv, shadow: withAlpha(COLORS.hrv, '28') },
		anytime: { color: COLORS.respiration, shadow: withAlpha(COLORS.respiration, '26') }
	};
	const SLOT_INDEX = Object.fromEntries(
		SLOT_ORDER.map((slot, index) => [slot, index])
	) as Record<SlotName, number>;
	const RENDERER_LABELS: Record<ScheduleOccurrence['renderer'], string> = {
		timer_session: 'Timer session',
		checklist_block: 'Checklist block',
		exercise_block: 'Exercise block'
	};

	const longDateFormat = new Intl.DateTimeFormat('en-US', {
		weekday: 'long',
		month: 'short',
		day: 'numeric'
	});
	const shortDateFormat = new Intl.DateTimeFormat('en-US', {
		month: 'short',
		day: 'numeric'
	});
	const weekdayFormat = new Intl.DateTimeFormat('en-US', { weekday: 'short' });

	let loading = $state(true);
	let error: string | null = $state(null);
	let lens = $state<LensMode>('day');
	let windowStartDate = $state(localDateIso());
	let selectedDate = $state(localDateIso());
	let selectedRoutineId = $state<string | null>(null);
	let scheduleWindow = $state<ScheduleWindow | null>(null);
	let routines = $state<RoutineSchedule[]>([]);
	let requestToken = 0;

	function readInitialScheduleState(): { startDate: string; selectedDate: string } {
		const fallback = localDateIso();
		const params = new URL(window.location.href).searchParams;
		const requestedDate = params.get('date');
		const requestedStartDate = params.get('start_date');
		const selectedDate =
			requestedDate && isIsoDateString(requestedDate) ? requestedDate : fallback;
		const startDate =
			requestedStartDate && isIsoDateString(requestedStartDate) ? requestedStartDate : selectedDate;
		return { startDate, selectedDate };
	}

	const allOccurrences = $derived.by(() =>
		scheduleWindow ? scheduleWindow.days.flatMap((day) => day.occurrences) : []
	);
	const routineOccurrenceCount = $derived.by(() => {
		const counts: Record<string, number> = {};
		for (const occurrence of allOccurrences) {
			counts[occurrence.routine_id] = (counts[occurrence.routine_id] ?? 0) + 1;
		}
		return counts;
	});
	const activeDays = $derived.by(
		() => scheduleWindow?.days.filter((day) => day.occurrences.length > 0).length ?? 0
	);
	const overlapDays = $derived.by(
		() => scheduleWindow?.days.filter((day) => day.occurrences.length > 1).length ?? 0
	);
	const routinesRepresented = $derived.by(
		() => new Set(allOccurrences.map((occurrence) => occurrence.routine_id)).size
	);
	const selectedDay = $derived.by(() => {
		if (!scheduleWindow) return null;
		return scheduleWindow.days.find((day) => day.date === selectedDate) ?? scheduleWindow.days[0] ?? null;
	});
	const selectedDaySections = $derived.by(() => groupOccurrencesBySlot(selectedDay?.occurrences ?? []));
	const selectedRoutine = $derived.by(
		() => routines.find((routine) => routine.id === selectedRoutineId) ?? routines[0] ?? null
	);
	const selectedRoutineOccurrences = $derived.by(() => {
		if (!selectedRoutine) return [];
		return allOccurrences
			.filter((occurrence) => occurrence.routine_id === selectedRoutine.id)
			.sort(sortOccurrences);
	});

	$effect(() => {
		if (!scheduleWindow?.days.length) return;
		if (scheduleWindow.days.some((day) => day.date === selectedDate)) return;
		selectedDate = scheduleWindow.days[0].date;
	});

	$effect(() => {
		if (!routines.length) {
			selectedRoutineId = null;
			return;
		}
		if (selectedRoutineId && routines.some((routine) => routine.id === selectedRoutineId)) {
			return;
		}
		selectedRoutineId = routines[0].id;
	});

	$effect(() => {
		if (!routines.length || !selectedRoutineId) return;
		if ((routineOccurrenceCount[selectedRoutineId] ?? 0) > 0) return;
		const nextVisibleRoutine = routines.find(
			(routine) => (routineOccurrenceCount[routine.id] ?? 0) > 0
		);
		if (nextVisibleRoutine) {
			selectedRoutineId = nextVisibleRoutine.id;
		}
	});

	function sortOccurrences(a: ScheduleOccurrence, b: ScheduleOccurrence): number {
		return (
			a.date.localeCompare(b.date) ||
			SLOT_INDEX[a.slot] - SLOT_INDEX[b.slot] ||
			a.position - b.position ||
			a.name.localeCompare(b.name)
		);
	}

	function toDate(date: string): Date {
		return new Date(`${date}T12:00:00`);
	}

	function addDays(date: string, delta: number): string {
		const next = toDate(date);
		next.setDate(next.getDate() + delta);
		return localDateIso(next);
	}

	function formatLongDate(date: string): string {
		return longDateFormat.format(toDate(date));
	}

	function formatShortDate(date: string): string {
		return shortDateFormat.format(toDate(date));
	}

	function formatWeekday(date: string): string {
		return weekdayFormat.format(toDate(date));
	}

	function formatDayNumber(date: string): string {
		return String(toDate(date).getDate());
	}

	function formatWindowRange(startDate: string, endDate: string): string {
		return `${formatShortDate(startDate)} to ${formatShortDate(endDate)}`;
	}

	function groupOccurrencesBySlot(occurrences: ScheduleOccurrence[]): SlotSection[] {
		const grouped: Record<SlotName, ScheduleOccurrence[]> = {
			morning: [],
			midday: [],
			evening: [],
			anytime: []
		};
		for (const occurrence of occurrences) {
			grouped[occurrence.slot].push(occurrence);
		}
		return SLOT_ORDER.map((slot) => ({
			slot,
			label: SLOT_LABELS[slot],
			color: SLOT_ACCENTS[slot].color,
			shadow: SLOT_ACCENTS[slot].shadow,
			items: grouped[slot].sort(sortOccurrences)
		}));
	}

	function rendererLabel(renderer: ScheduleOccurrence['renderer']): string {
		return RENDERER_LABELS[renderer];
	}

	function selectDay(date: string): void {
		selectedDate = date;
		lens = 'day';
	}

	function openRoutineLens(routineId: string): void {
		selectedRoutineId = routineId;
		lens = 'routine';
	}

	async function loadScheduleWindow(startDate: string): Promise<void> {
		const token = ++requestToken;
		error = null;
		const window = await api.getRoutineScheduleWindow(startDate);
		if (token !== requestToken) return;
		scheduleWindow = window;
		windowStartDate = window.start_date;
	}

	async function loadPage(): Promise<void> {
		error = null;
		const routinesResponse = await api.getRoutines('active');
		routines = routinesResponse.routines;
		const initialState = readInitialScheduleState();
		selectedDate = initialState.selectedDate;
		windowStartDate = initialState.startDate;
		await loadScheduleWindow(initialState.startDate);
	}

	async function moveWindow(delta: number): Promise<void> {
		const nextDate = addDays(windowStartDate, delta);
		selectedDate = nextDate;
		await loadScheduleWindow(nextDate);
	}

	async function submitWindowStart(): Promise<void> {
		selectedDate = windowStartDate;
		await loadScheduleWindow(windowStartDate);
	}

	onMount(() => {
		void loadPage()
			.catch((e: unknown) => {
				error = errorMessage(e);
			})
			.finally(() => {
				loading = false;
			});
	});
</script>

<svelte:head>
	<title>Routine Schedule - Garmin Stats</title>
</svelte:head>

{#if loading}
	<section class="loading-shell">
		<div class="loading-card">Resolving the next 14 days of live routine occurrences...</div>
	</section>
{:else}
	<section class="schedule-shell">
		<div class="hero">
			<div class="hero-copy">
				<p class="eyebrow">Phase 3 Schedule Review</p>
				<h1>Review the next two weeks as dated work, not recurrence metadata.</h1>
				<p class="hero-text">
					The day lens answers what lands on a date. The routine lens answers where one routine
					shows up across the same 14-day window. Both panels read the same resolved schedule.
				</p>
			</div>

			<div class="hero-aside">
				<div class="hero-stat">
					<span>Window span</span>
					<strong>{scheduleWindow ? scheduleWindow.days.length : 0}</strong>
					<small>days resolved by the backend</small>
				</div>
				<div class="hero-stat">
					<span>Scheduled cards</span>
					<strong>{allOccurrences.length}</strong>
					<small>dated occurrences in this view</small>
				</div>
				<div class="hero-stat">
					<span>Active days</span>
					<strong>{activeDays}</strong>
					<small>days with at least one card</small>
				</div>
				<div class="hero-stat accent">
					<span>Overlap days</span>
					<strong>{overlapDays}</strong>
					<small>days carrying more than one card</small>
				</div>
				<div class="hero-links">
					<a class="primary-link" href="/routines/creation">Open creation inbox</a>
					<a class="ghost-link" href="/today">Open today board</a>
				</div>
			</div>
		</div>

		{#if error}
			<div class="error-banner">{error}</div>
		{/if}

		<div class="control-bar">
			<div class="window-card">
				<div>
					<p class="eyebrow">Window</p>
					<h2>{scheduleWindow ? formatWindowRange(scheduleWindow.start_date, scheduleWindow.end_date) : 'No schedule loaded'}</h2>
				</div>

				<div class="window-tools">
					<button type="button" class="window-button" onclick={() => void moveWindow(-7)}>
						Back 7 days
					</button>
					<label class="date-control">
						<span>Window starts</span>
						<input type="date" bind:value={windowStartDate} onchange={() => void submitWindowStart()} />
					</label>
					<button type="button" class="window-button" onclick={() => void moveWindow(7)}>
						Forward 7 days
					</button>
				</div>
			</div>

			<div class="kpi-row">
				<div class="kpi-card">
					<span>Routines represented</span>
					<strong>{routinesRepresented}</strong>
				</div>
				<div class="kpi-card">
					<span>Selected day</span>
					<strong>{selectedDay?.occurrences.length ?? 0}</strong>
				</div>
				<div class="kpi-card">
					<span>Selected routine</span>
					<strong>{selectedRoutineOccurrences.length}</strong>
				</div>
			</div>
		</div>

		<div class="review-grid">
			<section class:panel={true} class:featured={lens === 'day'}>
				<div class="section-head">
					<div>
						<p class="eyebrow">Lens A</p>
						<h2>By day</h2>
					</div>
					<strong>{selectedDay ? formatLongDate(selectedDay.date) : 'No day selected'}</strong>
				</div>

				<div class="day-strip">
					{#each scheduleWindow?.days ?? [] as day}
						<button
							type="button"
							class:day-chip={true}
							class:selected={day.date === selectedDate}
							class:active={day.occurrences.length > 0}
							class:overlap={day.occurrences.length > 1}
							onclick={() => selectDay(day.date)}
						>
							<span>{formatWeekday(day.date)}</span>
							<strong>{formatDayNumber(day.date)}</strong>
							<small>{day.occurrences.length === 0 ? 'Clear' : `${day.occurrences.length} cards`}</small>
						</button>
					{/each}
				</div>

				{#if selectedDay}
					{#if selectedDay.occurrences.length === 0}
						<div class="empty-card">
							No cards land on {formatLongDate(selectedDay.date)}. This is a clear day in the current
							14-day window.
						</div>
					{:else}
						<div class="slot-grid">
							{#each selectedDaySections as section}
								<article class="slot-card">
									<div class="slot-head" style={`--slot-color: ${section.color}; --slot-shadow: ${section.shadow};`}>
										<div>
											<p class="eyebrow">{section.label}</p>
											<h3>{section.items.length}</h3>
										</div>
										<span>{section.items.length === 0 ? 'Open' : 'Scheduled'}</span>
									</div>

									{#if section.items.length === 0}
										<p class="slot-empty">No cards placed in this slot.</p>
									{:else}
										<div class="occurrence-list">
											{#each section.items as occurrence}
												<button
													type="button"
													class="occurrence-card"
													onclick={() => openRoutineLens(occurrence.routine_id)}
												>
													<div class="occurrence-topline">
														<div>
															<p>{occurrence.name}</p>
															<strong>{occurrence.routine_name}</strong>
														</div>
														<span>{rendererLabel(occurrence.renderer)}</span>
													</div>

													{#if occurrence.summary}
														<p class="occurrence-summary">{occurrence.summary}</p>
													{/if}

													<div class="occurrence-meta">
														<small>{SLOT_LABELS[occurrence.slot]} slot</small>
														<small>Position {occurrence.position}</small>
													</div>
												</button>
											{/each}
										</div>
									{/if}
								</article>
							{/each}
						</div>
					{/if}
				{/if}
			</section>

			<section class:panel={true} class:featured={lens === 'routine'}>
				<div class="section-head">
					<div>
						<p class="eyebrow">Lens B</p>
						<h2>By routine</h2>
					</div>
					<strong>{selectedRoutine ? selectedRoutine.name : 'No routine selected'}</strong>
				</div>

				{#if routines.length === 0}
					<div class="empty-card">
						No active routines exist yet. Activate a routine from the creation inbox to populate this
						view.
					</div>
				{:else}
					<div class="routine-switcher">
						{#each routines as routine}
							<button
								type="button"
								class:routine-pill={true}
								class:selected={routine.id === selectedRoutine?.id}
								class:muted={(routineOccurrenceCount[routine.id] ?? 0) === 0}
								onclick={() => openRoutineLens(routine.id)}
							>
								<span>{routine.name}</span>
								<small>{routineOccurrenceCount[routine.id] ?? 0} dates</small>
							</button>
						{/each}
					</div>

					{#if selectedRoutine}
						<article class="routine-summary">
							<div class="routine-topline">
								<div>
									<p class="eyebrow">{selectedRoutine.cadence}</p>
									<h3>{selectedRoutine.name}</h3>
								</div>
								<span>{selectedRoutineOccurrences.length === 0 ? 'Off window' : `${selectedRoutineOccurrences.length} stops`}</span>
							</div>

							<div class="routine-meta">
								<small>Starts {formatShortDate(selectedRoutine.start_date)}</small>
								<small>{selectedRoutine.end_date ? `Ends ${formatShortDate(selectedRoutine.end_date)}` : 'No end date'}</small>
								<small>{selectedRoutine.status}</small>
							</div>

							{#if selectedRoutine.notes}
								<p class="routine-note">{selectedRoutine.notes}</p>
							{/if}

							{#if selectedRoutine.tags.length > 0}
								<div class="tag-row">
									{#each selectedRoutine.tags as tag}
										<span>{tag}</span>
									{/each}
								</div>
							{/if}
						</article>

						{#if selectedRoutineOccurrences.length === 0}
							<div class="empty-card">
								{selectedRoutine.name} does not land inside this window. Shift the 14-day range to
								inspect where it reappears.
							</div>
						{:else}
							<div class="itinerary-list">
								{#each selectedRoutineOccurrences as occurrence}
									<article class="itinerary-card">
										<div class="itinerary-date">
											<span>{formatWeekday(occurrence.date)}</span>
											<strong>{formatShortDate(occurrence.date)}</strong>
										</div>

										<div class="itinerary-body">
											<p>{occurrence.name}</p>
											<div class="itinerary-meta">
												<small>{SLOT_LABELS[occurrence.slot]}</small>
												<small>{rendererLabel(occurrence.renderer)}</small>
												<small>Position {occurrence.position}</small>
											</div>

											{#if occurrence.summary}
												<p class="itinerary-summary">{occurrence.summary}</p>
											{/if}
										</div>
									</article>
								{/each}
							</div>
						{/if}
					{/if}
				{/if}
			</section>
		</div>
	</section>
{/if}

<style>
	:global(body) {
		color: #edf3f6;
		font-family: 'Avenir Next', 'Segoe UI', sans-serif;
	}

	.schedule-shell {
		--shell-bg: #0f1724;
		--card-bg: rgba(11, 20, 31, 0.72);
		--card-border: rgba(255, 255, 255, 0.08);
		--muted: #98abb8;
		--text: #edf3f6;
		display: flex;
		flex-direction: column;
		gap: 18px;
		color: var(--text);
	}

	.loading-shell {
		padding: 32px 0;
	}

	.loading-card,
	.error-banner,
	.empty-card {
		padding: 16px 18px;
		border-radius: 22px;
		border: 1px solid var(--card-border);
		background: rgba(255, 255, 255, 0.03);
		color: var(--muted);
		font-family: 'DM Mono', monospace;
		font-size: 12px;
		line-height: 1.6;
	}

	.hero,
	.window-card,
	.kpi-card,
	.panel,
	.routine-summary,
	.slot-card,
	.itinerary-card {
		border: 1px solid var(--card-border);
		background: var(--card-bg);
		backdrop-filter: blur(14px);
		box-shadow: 0 16px 42px rgba(0, 0, 0, 0.22);
	}

	.hero {
		position: relative;
		display: grid;
		grid-template-columns: minmax(0, 1.2fr) minmax(320px, 0.9fr);
		gap: 18px;
		padding: 24px;
		border-radius: 30px;
		background:
			radial-gradient(circle at top left, rgba(201, 147, 58, 0.18), transparent 34%),
			radial-gradient(circle at 90% 12%, rgba(99, 102, 176, 0.2), transparent 28%),
			radial-gradient(circle at bottom left, rgba(91, 181, 166, 0.12), transparent 38%),
			linear-gradient(145deg, rgba(10, 18, 28, 0.96), rgba(15, 23, 36, 0.9));
	}

	.hero::after {
		content: '';
		position: absolute;
		inset: 0;
		border-radius: inherit;
		background-image:
			linear-gradient(rgba(255, 255, 255, 0.02) 1px, transparent 1px),
			linear-gradient(90deg, rgba(255, 255, 255, 0.02) 1px, transparent 1px);
		background-size: 24px 24px;
		mask-image: linear-gradient(180deg, rgba(0, 0, 0, 0.72), transparent);
		pointer-events: none;
	}

	.hero-copy,
	.hero-aside,
	.slot-head,
	.occurrence-topline,
	.section-head,
	.routine-topline,
	.itinerary-card {
		position: relative;
		z-index: 1;
	}

	.hero-copy h1,
	.section-head h2,
	.slot-head h3,
	.routine-topline h3 {
		margin: 0;
		font-family: 'Iowan Old Style', 'Palatino Linotype', serif;
		font-weight: 700;
		letter-spacing: -0.03em;
	}

	.hero-copy h1 {
		margin-top: 8px;
		max-width: 13ch;
		font-size: clamp(2.2rem, 4vw, 4rem);
		line-height: 0.95;
	}

	.hero-text {
		max-width: 60ch;
		margin: 18px 0 0;
		color: #b8c7d1;
		line-height: 1.65;
		font-size: 1rem;
	}

	.eyebrow,
	.hero-stat span,
	.kpi-card span,
	.day-chip span,
	.slot-head span,
	.occurrence-topline span,
	.routine-pill small,
	.itinerary-date span,
	.routine-topline span {
		font-family: 'DM Mono', monospace;
		font-size: 11px;
		letter-spacing: 0.14em;
		text-transform: uppercase;
		color: #8da0ae;
	}

	.hero-aside {
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: 12px;
		align-content: start;
	}

	.hero-stat {
		padding: 16px;
		border-radius: 22px;
		border: 1px solid rgba(255, 255, 255, 0.08);
		background: rgba(255, 255, 255, 0.04);
	}

	.hero-stat strong,
	.kpi-card strong {
		display: block;
		margin-top: 10px;
		font-size: 30px;
		line-height: 1;
	}

	.hero-stat small,
	.slot-empty,
	.occurrence-summary,
	.routine-note,
	.itinerary-summary {
		color: #a7b8c3;
		line-height: 1.55;
	}

	.hero-stat.accent {
		background: linear-gradient(145deg, rgba(99, 102, 176, 0.22), rgba(201, 147, 58, 0.12));
	}

	.hero-links {
		grid-column: 1 / -1;
		display: flex;
		flex-wrap: wrap;
		gap: 10px;
		margin-top: 4px;
	}

	.primary-link,
	.ghost-link,
	.window-button,
	.day-chip,
	.routine-pill,
	.occurrence-card {
		transition:
			transform 140ms ease,
			border-color 140ms ease,
			background 140ms ease,
			box-shadow 140ms ease;
	}

	.primary-link,
	.ghost-link,
	.window-button {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		padding: 11px 14px;
		border-radius: 999px;
		font-family: 'DM Mono', monospace;
		font-size: 12px;
		letter-spacing: 0.04em;
		text-decoration: none;
		border: none;
		cursor: pointer;
	}

	.primary-link {
		background: linear-gradient(135deg, rgba(201, 147, 58, 0.98), rgba(99, 102, 176, 0.88));
		color: #08111c;
		font-weight: 700;
	}

	.ghost-link,
	.window-button {
		background: rgba(255, 255, 255, 0.05);
		color: #d6e1e8;
	}

	.primary-link:hover,
	.ghost-link:hover,
	.window-button:hover,
	.day-chip:hover,
	.routine-pill:hover,
	.occurrence-card:hover {
		transform: translateY(-1px);
	}

	.control-bar {
		display: grid;
		grid-template-columns: minmax(0, 1.2fr) minmax(280px, 0.8fr);
		gap: 14px;
	}

	.window-card {
		display: grid;
		grid-template-columns: minmax(0, 1fr) auto;
		gap: 16px;
		align-items: center;
		padding: 18px 20px;
		border-radius: 28px;
	}

	.window-card h2 {
		margin: 6px 0 0;
		font-size: clamp(1.4rem, 2.4vw, 2.1rem);
		font-family: 'Iowan Old Style', 'Palatino Linotype', serif;
		letter-spacing: -0.03em;
	}

	.window-tools,
	.kpi-row,
	.routine-meta,
	.tag-row,
	.occurrence-meta,
	.itinerary-meta {
		display: flex;
		flex-wrap: wrap;
		gap: 10px;
	}

	.date-control {
		display: grid;
		gap: 6px;
		color: #bfd0da;
		font-family: 'DM Mono', monospace;
		font-size: 11px;
		letter-spacing: 0.1em;
		text-transform: uppercase;
	}

	.date-control input {
		border-radius: 999px;
		border: 1px solid rgba(255, 255, 255, 0.1);
		background: rgba(255, 255, 255, 0.05);
		color: #edf3f6;
		padding: 11px 14px;
		font-family: 'DM Mono', monospace;
	}

	.kpi-row {
		display: grid;
		grid-template-columns: repeat(3, minmax(0, 1fr));
	}

	.kpi-card {
		padding: 16px 18px;
		border-radius: 22px;
	}

	.review-grid {
		display: grid;
		grid-template-columns: minmax(0, 1.15fr) minmax(340px, 0.85fr);
		gap: 16px;
		align-items: start;
	}

	.panel {
		display: flex;
		flex-direction: column;
		gap: 16px;
		padding: 18px;
		border-radius: 28px;
		opacity: 0.84;
	}

	.panel.featured {
		opacity: 1;
		border-color: rgba(255, 255, 255, 0.12);
	}

	.section-head {
		display: flex;
		align-items: flex-end;
		justify-content: space-between;
		gap: 14px;
	}

	.section-head h2 {
		margin-top: 8px;
		font-size: 2rem;
	}

	.section-head strong {
		color: #dce7ed;
		font-size: 0.96rem;
		text-align: right;
	}

	.day-strip {
		display: grid;
		grid-template-columns: repeat(7, minmax(0, 1fr));
		gap: 10px;
	}

	.day-chip {
		display: grid;
		gap: 6px;
		padding: 14px 12px;
		border-radius: 22px;
		border: 1px solid rgba(255, 255, 255, 0.06);
		background:
			linear-gradient(180deg, rgba(255, 255, 255, 0.045), rgba(255, 255, 255, 0.02)),
			rgba(255, 255, 255, 0.02);
		text-align: left;
		cursor: pointer;
	}

	.day-chip strong {
		font-size: 26px;
		line-height: 1;
	}

	.day-chip small {
		color: #97a9b6;
	}

	.day-chip.active {
		border-color: rgba(201, 147, 58, 0.26);
		background:
			radial-gradient(circle at top right, rgba(201, 147, 58, 0.12), transparent 55%),
			linear-gradient(180deg, rgba(255, 255, 255, 0.05), rgba(255, 255, 255, 0.025));
	}

	.day-chip.overlap {
		box-shadow: inset 0 0 0 1px rgba(99, 102, 176, 0.2);
	}

	.day-chip.selected {
		transform: translateY(-2px);
		border-color: rgba(99, 102, 176, 0.46);
		background:
			radial-gradient(circle at top right, rgba(99, 102, 176, 0.18), transparent 52%),
			linear-gradient(180deg, rgba(255, 255, 255, 0.08), rgba(255, 255, 255, 0.04));
		box-shadow: 0 14px 30px rgba(6, 10, 18, 0.28);
	}

	.slot-grid {
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: 14px;
	}

	.slot-card {
		padding: 14px;
		border-radius: 24px;
	}

	.slot-head {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 12px;
		padding: 14px;
		border-radius: 18px;
		background:
			radial-gradient(circle at top right, var(--slot-shadow), transparent 60%),
			linear-gradient(180deg, rgba(255, 255, 255, 0.04), rgba(255, 255, 255, 0.02));
	}

	.slot-head h3 {
		margin-top: 6px;
		font-size: 2rem;
		color: var(--slot-color);
	}

	.occurrence-list {
		display: flex;
		flex-direction: column;
		gap: 10px;
		margin-top: 12px;
	}

	.occurrence-card {
		display: grid;
		gap: 10px;
		padding: 14px;
		border-radius: 18px;
		border: 1px solid rgba(255, 255, 255, 0.06);
		background: rgba(255, 255, 255, 0.03);
		text-align: left;
		cursor: pointer;
	}

	.occurrence-topline {
		display: flex;
		align-items: flex-start;
		justify-content: space-between;
		gap: 12px;
	}

	.occurrence-topline p,
	.itinerary-body p {
		margin: 0;
		color: #eef5f8;
		font-size: 1.05rem;
		font-weight: 700;
	}

	.occurrence-topline strong {
		display: block;
		margin-top: 5px;
		color: #bfd0da;
		font-size: 0.95rem;
		font-weight: 500;
	}

	.routine-switcher {
		display: flex;
		flex-wrap: wrap;
		gap: 10px;
	}

	.routine-pill {
		padding: 11px 14px;
		border-radius: 999px;
		border: 1px solid rgba(255, 255, 255, 0.08);
		background: rgba(255, 255, 255, 0.04);
		color: #e7eef3;
		cursor: pointer;
	}

	.routine-pill span {
		display: block;
		font-size: 0.95rem;
		font-weight: 700;
	}

	.routine-pill.selected {
		border-color: rgba(91, 181, 166, 0.38);
		background:
			radial-gradient(circle at top right, rgba(91, 181, 166, 0.14), transparent 55%),
			rgba(255, 255, 255, 0.06);
	}

	.routine-pill.muted {
		opacity: 0.62;
	}

	.routine-summary {
		padding: 18px;
		border-radius: 22px;
	}

	.routine-topline,
	.itinerary-card {
		display: flex;
		align-items: flex-start;
		justify-content: space-between;
		gap: 12px;
	}

	.routine-topline h3 {
		margin-top: 8px;
		font-size: 1.9rem;
	}

	.routine-topline span {
		padding: 8px 10px;
		border-radius: 999px;
		border: 1px solid rgba(255, 255, 255, 0.08);
		background: rgba(255, 255, 255, 0.04);
	}

	.routine-meta small,
	.tag-row span,
	.occurrence-meta small,
	.itinerary-meta small {
		padding: 8px 10px;
		border-radius: 999px;
		background: rgba(255, 255, 255, 0.04);
		color: #bfd0da;
		font-family: 'DM Mono', monospace;
		font-size: 11px;
	}

	.routine-note,
	.itinerary-summary {
		margin: 12px 0 0;
	}

	.itinerary-list {
		display: flex;
		flex-direction: column;
		gap: 10px;
	}

	.itinerary-card {
		padding: 14px;
		border-radius: 20px;
	}

	.itinerary-date {
		min-width: 92px;
		display: grid;
		gap: 6px;
	}

	.itinerary-date strong {
		font-size: 1rem;
		color: #f1f5f7;
	}

	.itinerary-body {
		display: grid;
		gap: 10px;
	}

	@media (max-width: 1120px) {
		.hero,
		.control-bar,
		.review-grid {
			grid-template-columns: 1fr;
		}
	}

	@media (max-width: 760px) {
		.hero-aside,
		.kpi-row,
		.slot-grid {
			grid-template-columns: 1fr;
		}

		.window-card {
			grid-template-columns: 1fr;
		}

		.day-strip {
			grid-template-columns: repeat(2, minmax(0, 1fr));
		}

		.section-head,
		.itinerary-card,
		.routine-topline {
			flex-direction: column;
			align-items: flex-start;
		}
	}
</style>
