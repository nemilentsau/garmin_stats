<script lang="ts">
	import { onMount } from 'svelte';

	import {
		api,
		type ArtifactBundleSpec,
		type ArtifactBundlePreviewResponse,
		type ArtifactBundleImportResponse,
		type RoutineSchedule,
		type ScheduleOccurrence,
		type ScheduleWindow
	} from '$lib/api';
	import { COLORS, withAlpha } from '$lib/colors';
	import { addDays, isIsoDateString, localDateIso } from '$lib/date';
	import { errorMessage } from '$lib/utils';

	type SlotName = ScheduleOccurrence['slot'];

	type TimerPayload = {
		duration_minutes?: number;
		pattern?: string;
		instructions?: string;
		segments?: { label: string; duration_seconds: number }[];
	};

	type ChecklistPayload = {
		instructions?: string;
		items?: { id: string; label: string; detail?: string }[];
	};

	type ExercisePayload = {
		instructions?: string;
		exercises?: { id: string; label: string; detail?: string; reps?: string; duration_seconds?: number }[];
	};

	const SLOT_ORDER: SlotName[] = ['morning', 'midday', 'evening', 'anytime'];
	const SLOT_LABELS: Record<SlotName, string> = {
		morning: 'Morning',
		midday: 'Midday',
		evening: 'Evening',
		anytime: 'Anytime'
	};
	const SLOT_ACCENTS: Record<SlotName, { color: string; shadow: string }> = {
		morning: { color: COLORS.respiration, shadow: withAlpha(COLORS.respiration, '30') },
		midday: { color: COLORS.spo2, shadow: withAlpha(COLORS.spo2, '30') },
		evening: { color: COLORS.hrv, shadow: withAlpha(COLORS.hrv, '30') },
		anytime: { color: COLORS.stress, shadow: withAlpha(COLORS.stress, '30') }
	};
	const SLOT_INDEX = Object.fromEntries(
		SLOT_ORDER.map((slot, index) => [slot, index])
	) as Record<SlotName, number>;
	const RENDERER_ICONS: Record<ScheduleOccurrence['renderer'], string> = {
		exercise_block: '\u{1F4AA}',
		timer_session: '\u{23F1}',
		checklist_block: '\u{2611}'
	};

	let loading = $state(true);
	let error: string | null = $state(null);
	let windowStartDate = $state(localDateIso());
	let selectedRoutineId = $state<string | null>(null);
	let scheduleWindow = $state<ScheduleWindow | null>(null);
	let routines = $state<RoutineSchedule[]>([]);
	let expandedOccurrenceKey = $state<string | null>(null);
	/** Map of occurrence_key → completion status from card logs. */
	let completionMap = $state<Record<string, string>>({});
	let requestToken = 0;

	function occStatus(occ: ScheduleOccurrence): string {
		return completionMap[occ.occurrence_key] ?? 'pending';
	}

	const allOccurrences = $derived.by(() =>
		scheduleWindow ? scheduleWindow.days.flatMap((day) => day.occurrences) : []
	);

	const routineOccurrenceCount = $derived.by(() => {
		const counts: Record<string, number> = {};
		for (const occ of allOccurrences) {
			if (!occ.routine_id) continue;
			counts[occ.routine_id] = (counts[occ.routine_id] ?? 0) + 1;
		}
		return counts;
	});

	const selectedRoutine = $derived.by(() => {
		if (!selectedRoutineId) return null;
		return routines.find((r) => r.id === selectedRoutineId) ?? null;
	});

	const selectedRoutineOccurrences = $derived.by(() => {
		if (!selectedRoutine) return [];
		return allOccurrences
			.filter((occ) => occ.routine_id === selectedRoutine.id)
			.sort(sortOccurrences);
	});

	const routineTimelineDays = $derived.by(() => {
		if (!selectedRoutine) return [];
		const byDate = new Map<string, ScheduleOccurrence[]>();
		for (const occ of selectedRoutineOccurrences) {
			const list = byDate.get(occ.date) ?? [];
			list.push(occ);
			byDate.set(occ.date, list);
		}
		return [...byDate.entries()]
			.sort(([a], [b]) => a.localeCompare(b))
			.map(([date, occurrences]) => ({ date, occurrences }));
	});

	type RoutineGroup = { routineName: string; occurrences: ScheduleOccurrence[] };
	type TimelineDay = { date: string; groups: RoutineGroup[] };

	/** Combined timeline — grouped by routine within each day. */
	const combinedTimelineDays = $derived.by((): TimelineDay[] => {
		const sorted = [...allOccurrences].sort(sortOccurrences);
		const byDate = new Map<string, Map<string, ScheduleOccurrence[]>>();
		for (const occ of sorted) {
			const rName = occ.routine_name ?? 'Schedule override';
			if (!byDate.has(occ.date)) byDate.set(occ.date, new Map());
			const dateMap = byDate.get(occ.date)!;
			if (!dateMap.has(rName)) dateMap.set(rName, []);
			dateMap.get(rName)!.push(occ);
		}
		return [...byDate.entries()]
			.sort(([a], [b]) => a.localeCompare(b))
			.map(([date, routineMap]) => ({
				date,
				groups: [...routineMap.entries()].map(([routineName, occurrences]) => ({ routineName, occurrences }))
			}));
	});

	/** Single routine timeline — one group per day. */
	const singleRoutineTimelineDays = $derived.by((): TimelineDay[] => {
		return routineTimelineDays.map((day) => ({
			date: day.date,
			groups: [{ routineName: '', occurrences: day.occurrences }]
		}));
	});

	/** Which timeline days to show. */
	const timelineDays = $derived(selectedRoutineId ? singleRoutineTimelineDays : combinedTimelineDays);
	const showRoutineLabel = $derived(!selectedRoutineId);

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

	const shortDateFormat = new Intl.DateTimeFormat('en-US', { month: 'short', day: 'numeric' });
	const weekdayFormat = new Intl.DateTimeFormat('en-US', { weekday: 'short' });
	const weekdayLongFormat = new Intl.DateTimeFormat('en-US', { weekday: 'long' });

	function formatShortDate(date: string): string {
		return shortDateFormat.format(toDate(date));
	}
	function formatWeekday(date: string): string {
		return weekdayFormat.format(toDate(date));
	}
	function formatWeekdayLong(date: string): string {
		return weekdayLongFormat.format(toDate(date));
	}
	function formatWindowRange(start: string, end: string): string {
		return `${formatShortDate(start)} \u2013 ${formatShortDate(end)}`;
	}

	function cardBrief(occ: ScheduleOccurrence): string {
		const p = occ.payload_json as Record<string, unknown>;
		if (occ.renderer === 'timer_session') {
			const dur = p?.duration_minutes as number | undefined;
			return dur ? `${dur} min` : '';
		}
		if (occ.renderer === 'exercise_block') {
			const ex = (p?.exercises as unknown[]) ?? [];
			return ex.length ? `${ex.length} exercises` : '';
		}
		const items = (p?.items as unknown[]) ?? [];
		return items.length ? `${items.length} items` : '';
	}

	function timerPayload(p: Record<string, unknown>): TimerPayload {
		return p as unknown as TimerPayload;
	}
	function exercisePayload(p: Record<string, unknown>): ExercisePayload {
		return p as unknown as ExercisePayload;
	}
	function checklistPayload(p: Record<string, unknown>): ChecklistPayload {
		return p as unknown as ChecklistPayload;
	}

	function readInitialState(): { startDate: string; routineId: string | null } {
		const params = new URL(window.location.href).searchParams;
		const reqStart = params.get('start_date');
		const startDate = reqStart && isIsoDateString(reqStart) ? reqStart : localDateIso();
		const routineId = params.get('routine') ?? null;
		return { startDate, routineId };
	}

	async function loadScheduleWindow(startDate: string): Promise<void> {
		const token = ++requestToken;
		error = null;
		const [win, logs] = await Promise.all([
			api.getRoutineScheduleWindow(startDate),
			api.getCardLogsRange(startDate, addDays(startDate, 13)),
		]);
		if (token !== requestToken) return;
		scheduleWindow = win;
		windowStartDate = win.start_date;
		const map: Record<string, string> = {};
		for (const entry of logs.entries) {
			map[entry.occurrence_key] = entry.status;
		}
		completionMap = map;
	}

	async function loadPage(): Promise<void> {
		error = null;
		const res = await api.getRoutines('active');
		routines = res.routines;
		const initial = readInitialState();
		windowStartDate = initial.startDate;
		if (initial.routineId && routines.some((r) => r.id === initial.routineId)) {
			selectedRoutineId = initial.routineId;
		}
		await loadScheduleWindow(initial.startDate);
	}

	async function moveWindow(delta: number): Promise<void> {
		expandedOccurrenceKey = null;
		await loadScheduleWindow(addDays(windowStartDate, delta));
	}

	async function submitWindowStart(): Promise<void> {
		expandedOccurrenceKey = null;
		await loadScheduleWindow(windowStartDate);
	}

	/* ── Import modal ── */
	type ImportStep = 'idle' | 'previewing' | 'preview-ok' | 'preview-error' | 'importing' | 'done';
	let importModalOpen = $state(false);
	let importStep = $state<ImportStep>('idle');
	let importBundle = $state<ArtifactBundleSpec | null>(null);
	let importPreview = $state<ArtifactBundlePreviewResponse | null>(null);
	let importResult = $state<ArtifactBundleImportResponse | null>(null);
	let importError = $state<string | null>(null);
	let importStartDate = $state(localDateIso());
	let fileInputEl: HTMLInputElement | undefined = $state();

	function openImportModal(): void {
		importModalOpen = true;
		importStep = 'idle';
		importBundle = null;
		importPreview = null;
		importResult = null;
		importError = null;
		importStartDate = localDateIso();
	}

	function closeImportModal(): void {
		importModalOpen = false;
	}

	async function handleFile(file: File): Promise<void> {
		importError = null;
		try {
			const text = await file.text();
			const bundle = JSON.parse(text) as ArtifactBundleSpec;
			importBundle = bundle;
			importStep = 'previewing';
			const preview = await api.previewAssistantArtifactBundle(bundle);
			importPreview = preview;
			importStep = preview.valid ? 'preview-ok' : 'preview-error';
		} catch (e: unknown) {
			importError = errorMessage(e);
			importStep = 'idle';
		}
	}

	function onFileInput(e: Event): void {
		const input = e.currentTarget as HTMLInputElement;
		const file = input.files?.[0];
		if (file) void handleFile(file);
		input.value = '';
	}

	function onDrop(e: DragEvent): void {
		e.preventDefault();
		const file = e.dataTransfer?.files[0];
		if (file && file.name.endsWith('.json')) void handleFile(file);
	}

	function shiftBundleDates(bundle: ArtifactBundleSpec): ArtifactBundleSpec {
		const shifted = $state.snapshot(bundle) as ArtifactBundleSpec;
		const newStart = toDate(importStartDate);
		for (const routine of shifted.routine_specs ?? []) {
			if (!routine.start_date) continue;
			const origStart = toDate(routine.start_date);
			const deltaMs = newStart.getTime() - origStart.getTime();
			routine.start_date = importStartDate;
			if (routine.end_date) {
				const origEnd = toDate(routine.end_date);
				const newEnd = new Date(origEnd.getTime() + deltaMs);
				routine.end_date = localDateIso(newEnd);
			}
		}
		return shifted;
	}

	async function handleImport(): Promise<void> {
		if (!importBundle) return;
		importError = null;
		try {
			importStep = 'importing';
			const bundleToImport = shiftBundleDates(importBundle);
			const result = await api.importAssistantArtifactBundle(bundleToImport);
			importResult = result;
			importStep = 'done';
			const res = await api.getRoutines('active');
			routines = res.routines;
			await loadScheduleWindow(windowStartDate);
		} catch (e: unknown) {
			importError = errorMessage(e);
			importStep = 'preview-ok';
		}
	}

	function resetImport(): void {
		importStep = 'idle';
		importBundle = null;
		importPreview = null;
		importError = null;
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
		<div class="loading-card">Resolving the next 14 days of routine occurrences...</div>
	</section>
{:else}
	<section class="schedule-shell">
		<!-- Header bar -->
		<div class="header-bar">
			<div class="header-left">
				<h1>Routine Schedule</h1>
				{#if scheduleWindow}
					<span class="window-range">{formatWindowRange(scheduleWindow.start_date, scheduleWindow.end_date)}</span>
				{/if}
			</div>
			<div class="header-right">
				<button type="button" class="nav-btn" onclick={() => void moveWindow(-7)} title="Back 7 days">
					<svg viewBox="0 0 16 16" width="14" height="14" fill="none">
						<path d="M10 3L5 8L10 13" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
					</svg>
				</button>
				<input type="date" class="date-input" bind:value={windowStartDate} onchange={() => void submitWindowStart()} />
				<button type="button" class="nav-btn" onclick={() => void moveWindow(7)} title="Forward 7 days">
					<svg viewBox="0 0 16 16" width="14" height="14" fill="none">
						<path d="M6 3L11 8L6 13" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
					</svg>
				</button>
				<button type="button" class="import-btn" onclick={openImportModal}>Import</button>
			</div>
		</div>

		{#if error}
			<div class="error-banner">{error}</div>
		{/if}

		<!-- Routine selector -->
		<div class="filter-row">
			<select
				class="routine-select"
				value={selectedRoutineId ?? ''}
				onchange={(e) => {
					selectedRoutineId = e.currentTarget.value || null;
					expandedOccurrenceKey = null;
				}}
			>
				<option value="">All routines ({routines.length})</option>
				{#each routines as routine}
					<option value={routine.id}>{routine.name} ({routineOccurrenceCount[routine.id] ?? 0} in window)</option>
				{/each}
			</select>
		</div>

		<!-- Content -->
		{#if selectedRoutine}
			<!-- Routine header (single routine selected) -->
			<div class="routine-header">
				<div class="routine-header-left">
					<h2>{selectedRoutine.name}</h2>
					<div class="routine-meta">
						<span>{formatShortDate(selectedRoutine.start_date)}{selectedRoutine.end_date ? ` \u2013 ${formatShortDate(selectedRoutine.end_date)}` : ' \u2013 ongoing'}</span>
						<span class="status-badge" class:active={selectedRoutine.status === 'active'}>{selectedRoutine.status}</span>
					</div>
				</div>
				{#if selectedRoutine.tags.length > 0}
					<div class="tag-row">
						{#each selectedRoutine.tags as tag}
							<span class="mini-tag">{tag}</span>
						{/each}
					</div>
				{/if}
				{#if selectedRoutine.notes}
					<p class="routine-notes">{selectedRoutine.notes}</p>
				{/if}
			</div>
		{/if}

		{#if timelineDays.length === 0}
			<div class="empty-state">
				{#if selectedRoutine}
					{selectedRoutine.name} has no occurrences in this 14-day window. Shift the window to find it.
				{:else}
					No occurrences in this 14-day window.
				{/if}
			</div>
		{:else}
			<div class="timeline-list">
				{#each timelineDays as day}
					<div class="timeline-day">
						<div class="timeline-date">
							<span class="timeline-weekday">{formatWeekday(day.date)}</span>
							<span class="timeline-day-num">{formatShortDate(day.date)}</span>
						</div>
						<div class="timeline-cards">
							{#each day.groups as group}
								{#if showRoutineLabel}
									<div class="routine-divider">{group.routineName}</div>
								{/if}
								{#each group.occurrences as occ}
									{@const accent = SLOT_ACCENTS[occ.slot]}
									{@const isExpanded = expandedOccurrenceKey === occ.occurrence_key}
									{@const status = occStatus(occ)}
									<div class="timeline-card" class:expanded={isExpanded} class:done={status === 'completed'} class:skipped={status === 'skipped'} class:partial={status === 'partial'} style={`--tc-color: ${accent.color}; --tc-shadow: ${accent.shadow}`}>
										<button type="button" class="timeline-card-main" onclick={() => (expandedOccurrenceKey = isExpanded ? null : occ.occurrence_key)}>
											{#if status === 'completed'}
												<span class="status-check done-check">
													<svg viewBox="0 0 16 16" width="12" height="12" fill="none"><path d="M3.5 8.5L6.5 11.5L12.5 4.5" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>
												</span>
											{:else if status === 'skipped'}
												<span class="status-check skip-check">
													<svg viewBox="0 0 16 16" width="10" height="10" fill="none"><path d="M4 4L12 12M12 4L4 12" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>
												</span>
											{:else if status === 'partial'}
												<span class="status-check partial-check">
													<svg viewBox="0 0 16 16" width="10" height="10" fill="none"><path d="M3 8H13" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>
												</span>
											{/if}
											<div class="card-content">
												<span class="card-name">{occ.name}</span>
												{#if occ.summary}
													<span class="card-summary">{occ.summary}</span>
												{/if}
											</div>
										<span class="card-brief">{cardBrief(occ)}</span>
										<div class="card-badges">
											<span class="slot-badge" style={`--sb-color: ${accent.color}`}>{SLOT_LABELS[occ.slot]}</span>
										</div>
										<svg class="expand-chevron" class:rotated={isExpanded} viewBox="0 0 16 16" width="14" height="14" fill="none">
											<path d="M4 6L8 10L12 6" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
											</svg>
										</button>

										{#if isExpanded}
											<div class="detail-panel">
												{#if occ.renderer === 'timer_session'}
													{@const tp = timerPayload(occ.payload_json as Record<string, unknown>)}
													{#if tp.instructions}
														<p class="detail-copy">{tp.instructions}</p>
													{/if}
													{#if tp.segments?.length}
														<div class="detail-list">
															{#each tp.segments as seg}
																<div class="detail-row">
																	<span>{seg.label}</span>
																	<span class="detail-meta">{Math.round(seg.duration_seconds / 60)} min</span>
																</div>
															{/each}
														</div>
													{/if}
												{:else if occ.renderer === 'exercise_block'}
													{@const ep = exercisePayload(occ.payload_json as Record<string, unknown>)}
													{#if ep.instructions}
														<p class="detail-copy">{ep.instructions}</p>
													{/if}
													{#if ep.exercises?.length}
														<div class="detail-list">
															{#each ep.exercises as ex}
																<div class="detail-row">
																	<div class="detail-row-content">
																		<strong>{ex.label}</strong>
																		{#if ex.detail}
																			<small>{ex.detail}</small>
																		{/if}
																	</div>
																</div>
															{/each}
														</div>
													{/if}
												{:else}
													{@const cp = checklistPayload(occ.payload_json as Record<string, unknown>)}
													{#if cp.instructions}
														<p class="detail-copy">{cp.instructions}</p>
													{/if}
													{#if cp.items?.length}
														<div class="detail-list">
															{#each cp.items as item}
																<div class="detail-row">
																	<div class="detail-row-content">
																		<strong>{item.label}</strong>
																		{#if item.detail}
																			<small>{item.detail}</small>
																		{/if}
																	</div>
																</div>
															{/each}
														</div>
													{/if}
												{/if}

												{#if occ.tags.length > 0}
													<div class="tag-row">
														{#each occ.tags as tag}
															<span class="mini-tag">{tag}</span>
														{/each}
													</div>
												{/if}
											</div>
										{/if}
									</div>
								{/each}
							{/each}
							</div>
						</div>
					{/each}
				</div>
			{/if}
	</section>
{/if}

<!-- Import modal -->
{#if importModalOpen}
	<!-- svelte-ignore a11y_click_events_have_key_events a11y_no_static_element_interactions a11y_no_noninteractive_element_interactions a11y_interactive_supports_focus -->
	<div class="modal-backdrop" role="dialog" tabindex="-1" onclick={(e) => { if (e.target === e.currentTarget) closeImportModal(); }}>
		<div class="modal-panel">
			<div class="modal-header">
				<h2>Import Routine Bundle</h2>
				<button type="button" class="modal-close" onclick={closeImportModal} title="Close">
					<svg viewBox="0 0 16 16" width="14" height="14" fill="none">
						<path d="M4 4L12 12M12 4L4 12" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
					</svg>
				</button>
			</div>

			{#if importStep === 'idle'}
				<!-- svelte-ignore a11y_click_events_have_key_events a11y_no_static_element_interactions a11y_no_noninteractive_element_interactions -->
				<div
					class="drop-zone"
					role="button"
					tabindex="0"
					ondrop={onDrop}
					ondragover={(e) => e.preventDefault()}
					onclick={() => fileInputEl?.click()}
				>
					<svg viewBox="0 0 24 24" width="32" height="32" fill="none">
						<path d="M12 16V4M12 4L8 8M12 4L16 8" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
						<path d="M20 16V18C20 19.1 19.1 20 18 20H6C4.9 20 4 19.1 4 18V16" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
					</svg>
					<span>Drop a <strong>.json</strong> bundle here or click to browse</span>
				</div>
				<input type="file" accept=".json" class="file-input-hidden" bind:this={fileInputEl} onchange={onFileInput} />
				{#if importError}
					<div class="import-error">{importError}</div>
				{/if}

			{:else if importStep === 'previewing'}
				<div class="import-status">Validating bundle...</div>

			{:else if importStep === 'preview-ok' && importPreview && importBundle}
				<div class="preview-summary">
					<div class="preview-name">{importBundle.name}</div>
					<div class="preview-stats">
						<span>{importBundle.card_templates?.length ?? 0} card templates</span>
						<span>{importBundle.routine_specs?.length ?? 0} routines</span>
						<span>{importBundle.routine_specs?.reduce((n, r) => n + (r.assignments?.length ?? 0), 0) ?? 0} assignments</span>
					</div>
					<div class="start-date-field">
						<span>Start date</span>
						<input type="date" class="date-input" bind:value={importStartDate} />
					</div>
					{#if importPreview.deltas.length > 0}
						<div class="delta-list">
							{#each importPreview.deltas as delta}
								<div class="delta-row">
									<span class="delta-action" class:create={delta.action === 'create'} class:update={delta.action === 'update'}>{delta.action}</span>
									<span>{delta.summary}</span>
								</div>
							{/each}
						</div>
					{/if}
					{#if importError}
						<div class="import-error">{importError}</div>
					{/if}
				</div>
				<div class="modal-actions">
					<button type="button" class="action-btn primary" onclick={() => void handleImport()}>Import</button>
					<button type="button" class="action-btn ghost" onclick={closeImportModal}>Cancel</button>
				</div>

			{:else if importStep === 'preview-error' && importPreview}
				<div class="preview-summary">
					<div class="preview-name">{importBundle?.name ?? 'Bundle'}</div>
					<div class="issue-list">
						{#each importPreview.issues as issue}
							<div class="issue-row">
								<span class="issue-path">{issue.path}</span>
								<span>{issue.message}</span>
							</div>
						{/each}
					</div>
				</div>
				<div class="modal-actions">
					<button type="button" class="action-btn ghost" onclick={resetImport}>Try another file</button>
					<button type="button" class="action-btn ghost" onclick={closeImportModal}>Cancel</button>
				</div>

			{:else if importStep === 'importing'}
				<div class="import-status">Importing...</div>

			{:else if importStep === 'done' && importResult}
				<div class="preview-summary">
					<div class="import-success">Imported {importResult.total_imported} artifacts</div>
					{#if importResult.deltas.length > 0}
						<div class="delta-list">
							{#each importResult.deltas as delta}
								<div class="delta-row">
									<span class="delta-action" class:create={delta.action === 'create'} class:update={delta.action === 'update'}>{delta.action}</span>
									<span>{delta.summary}</span>
								</div>
							{/each}
						</div>
					{/if}
				</div>
				<div class="modal-actions">
					<button type="button" class="action-btn primary" onclick={closeImportModal}>Done</button>
				</div>
			{/if}
		</div>
	</div>
{/if}

<style>
	.schedule-shell {
		--paper: rgba(255, 255, 255, 0.035);
		--paper-border: rgba(255, 255, 255, 0.08);
		--muted: #7f95a6;
		display: flex;
		flex-direction: column;
		gap: 12px;
	}

	.loading-shell {
		padding: 32px 0;
	}

	.loading-card,
	.error-banner,
	.empty-state {
		font-family: 'DM Mono', monospace;
		font-size: 12px;
		color: #8fa3b0;
		border: 1px solid rgba(255, 255, 255, 0.08);
		background: rgba(255, 255, 255, 0.02);
		border-radius: 12px;
		padding: 12px 14px;
	}

	.error-banner {
		color: #f2a399;
		border-color: rgba(232, 93, 74, 0.3);
		background: rgba(232, 93, 74, 0.08);
	}

	/* ── Header bar ── */
	.header-bar {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 16px;
		padding: 12px 16px;
		border-radius: 14px;
		background: rgba(255, 255, 255, 0.03);
		border: 1px solid var(--paper-border);
	}

	.header-left {
		display: flex;
		align-items: center;
		gap: 14px;
	}

	.header-left h1 {
		margin: 0;
		font-family: 'Instrument Sans', sans-serif;
		font-size: 20px;
		font-weight: 600;
		color: #eef5f8;
	}

	.window-range {
		font-family: 'DM Mono', monospace;
		font-size: 12px;
		color: var(--muted);
	}

	.header-right {
		display: flex;
		align-items: center;
		gap: 6px;
	}

	.nav-btn {
		width: 30px;
		height: 30px;
		border-radius: 6px;
		border: 1px solid rgba(255, 255, 255, 0.06);
		background: transparent;
		color: #6b8292;
		cursor: pointer;
		display: flex;
		align-items: center;
		justify-content: center;
		transition: background 0.15s, color 0.15s;
	}

	.nav-btn:hover {
		background: rgba(255, 255, 255, 0.06);
		color: #c3d3dd;
	}

	.date-input {
		border: 1px solid rgba(255, 255, 255, 0.1);
		background: rgba(8, 15, 24, 0.7);
		color: #c3d3dd;
		border-radius: 8px;
		padding: 6px 10px;
		font-family: 'DM Mono', monospace;
		font-size: 12px;
	}

	/* ── Filter / selector row ── */
	.filter-row {
		display: flex;
		align-items: center;
		gap: 6px;
		flex-wrap: wrap;
	}

	.routine-select {
		padding: 5px 28px 5px 12px;
		border-radius: 8px;
		border: 1px solid rgba(255, 255, 255, 0.08);
		background: rgba(255, 255, 255, 0.04);
		color: #c8d6df;
		font-family: 'DM Mono', monospace;
		font-size: 11px;
		letter-spacing: 0.04em;
		cursor: pointer;
		appearance: none;
		background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='10' height='6'%3E%3Cpath d='M0 0l5 6 5-6z' fill='%238fa3b0'/%3E%3C/svg%3E");
		background-repeat: no-repeat;
		background-position: right 10px center;
		transition: border-color 0.15s, background 0.15s;
	}
	.routine-select:hover { border-color: rgba(255, 255, 255, 0.15); }
	.routine-select:focus { outline: none; border-color: rgba(91, 181, 166, 0.4); }
	.routine-select option { background: #1a2632; color: #c8d6df; }

.mini-tag {
		padding: 2px 7px;
		border-radius: 4px;
		background: rgba(255, 255, 255, 0.05);
		font-family: 'DM Mono', monospace;
		font-size: 10px;
		color: #8fa3b0;
	}

	.tag-row {
		display: flex;
		gap: 4px;
		flex-wrap: wrap;
	}

	/* ── Routine header ── */
	.routine-header {
		padding: 12px 16px;
		border-radius: 10px;
		background: rgba(255, 255, 255, 0.025);
		border: 1px solid rgba(255, 255, 255, 0.05);
		display: flex;
		flex-direction: column;
		gap: 8px;
	}

	.routine-header-left {
		display: flex;
		flex-direction: column;
		gap: 4px;
	}

	.routine-header h2 {
		margin: 0;
		font-family: 'Instrument Sans', sans-serif;
		font-size: 16px;
		font-weight: 600;
		color: #eef5f8;
	}

	.routine-meta {
		display: flex;
		align-items: center;
		gap: 8px;
		font-family: 'DM Mono', monospace;
		font-size: 11px;
		color: var(--muted);
	}

	.status-badge {
		padding: 2px 7px;
		border-radius: 4px;
		background: rgba(255, 255, 255, 0.05);
		font-size: 10px;
		text-transform: uppercase;
		letter-spacing: 0.08em;
	}

	.status-badge.active {
		color: #5bb5a6;
		background: rgba(91, 181, 166, 0.12);
	}

	.routine-notes {
		margin: 0;
		font-size: 12px;
		color: #a7bac6;
		line-height: 1.4;
	}

	/* ── Timeline ── */
	.timeline-list {
		display: flex;
		flex-direction: column;
		gap: 0;
	}

	.timeline-day {
		display: flex;
		gap: 0;
		padding-top: 12px;
	}

	.timeline-day + .timeline-day {
		border-top: 1px solid rgba(255, 255, 255, 0.06);
	}

	.timeline-date {
		flex-shrink: 0;
		width: 72px;
		display: flex;
		flex-direction: column;
		align-items: flex-end;
		justify-content: flex-start;
		padding: 12px 12px 12px 0;
		gap: 1px;
	}

	.timeline-weekday {
		font-family: 'DM Mono', monospace;
		font-size: 10px;
		text-transform: uppercase;
		letter-spacing: 0.1em;
		color: var(--muted);
	}

	.timeline-day-num {
		font-family: 'DM Mono', monospace;
		font-size: 12px;
		color: #c3d3dd;
	}

	.timeline-cards {
		flex: 1;
		min-width: 0;
		display: flex;
		flex-direction: column;
		gap: 2px;
	}

	.routine-divider {
		font-family: 'DM Mono', monospace;
		font-size: 10px;
		letter-spacing: 0.1em;
		text-transform: uppercase;
		color: var(--muted);
		padding: 8px 0 4px;
		margin-top: 4px;
	}

	.routine-divider:first-child {
		margin-top: 0;
	}

	.timeline-card {
		border-radius: 10px;
		background: rgba(255, 255, 255, 0.025);
		border: 1px solid rgba(255, 255, 255, 0.05);
		border-left: 3px solid var(--tc-color);
		transition: background 0.15s;
	}

	.timeline-card:hover {
		background: rgba(255, 255, 255, 0.045);
	}

	.timeline-card.done { opacity: 0.45; }
	.timeline-card.done:hover { opacity: 0.7; }
	.timeline-card.skipped { opacity: 0.35; }
	.timeline-card.skipped:hover { opacity: 0.6; }
	.timeline-card.partial { opacity: 0.6; }

	.timeline-card.done .card-name {
		text-decoration: line-through;
		text-decoration-color: rgba(91, 181, 166, 0.5);
	}
	.timeline-card.skipped .card-name {
		text-decoration: line-through;
		text-decoration-color: rgba(232, 93, 74, 0.4);
	}

	.timeline-card.expanded {
		opacity: 1;
		background: rgba(255, 255, 255, 0.04);
		border-color: rgba(255, 255, 255, 0.1);
		border-left-color: var(--tc-color);
	}

	.status-check {
		flex-shrink: 0;
		width: 22px;
		height: 22px;
		border-radius: 5px;
		display: flex;
		align-items: center;
		justify-content: center;
	}
	.done-check { background: rgba(91, 181, 166, 0.2); color: #7be0d0; }
	.skip-check { background: rgba(232, 93, 74, 0.12); color: #f2a399; }
	.partial-check { background: rgba(212, 148, 76, 0.15); color: #f3bf81; }

	.timeline-card-main {
		display: flex;
		align-items: center;
		gap: 10px;
		padding: 10px 14px;
		width: 100%;
		background: none;
		border: none;
		color: inherit;
		cursor: pointer;
		text-align: left;
	}

	.card-content {
		flex: 1;
		min-width: 0;
		display: flex;
		flex-direction: column;
		gap: 1px;
	}

	.card-name {
		font-family: 'Instrument Sans', sans-serif;
		font-size: 14px;
		font-weight: 600;
		color: #eef5f8;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}

	.card-summary {
		font-size: 12px;
		color: #8fa3b0;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}

	.card-brief {
		flex-shrink: 0;
		font-family: 'DM Mono', monospace;
		font-size: 11px;
		color: #6b8292;
	}

	.card-badges {
		display: flex;
		gap: 4px;
		flex-shrink: 0;
	}

	.slot-badge {
		padding: 2px 7px;
		border-radius: 4px;
		background: rgba(255, 255, 255, 0.05);
		font-family: 'DM Mono', monospace;
		font-size: 10px;
		color: var(--sb-color);
	}

	.expand-chevron {
		flex-shrink: 0;
		color: #6b8292;
		transition: transform 0.2s ease;
	}

	.expand-chevron.rotated {
		transform: rotate(180deg);
	}

	/* ── Detail panel (read-only) ── */
	.detail-panel {
		padding: 12px 14px 14px;
		border-top: 1px solid rgba(255, 255, 255, 0.06);
		display: flex;
		flex-direction: column;
		gap: 12px;
	}

	.detail-copy {
		margin: 0;
		color: #a7bac6;
		font-size: 13px;
		line-height: 1.5;
	}

	.detail-list {
		display: grid;
		gap: 6px;
	}

	.detail-row {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 10px;
		padding: 8px 10px;
		border-radius: 8px;
		background: rgba(255, 255, 255, 0.03);
		font-size: 13px;
	}

	.detail-row-content {
		display: flex;
		flex-direction: column;
		gap: 2px;
	}

	.detail-row-content strong {
		font-size: 13px;
		color: #eef5f8;
	}

	.detail-row-content small {
		color: #6b8292;
		font-size: 11px;
	}

	.detail-meta {
		font-family: 'DM Mono', monospace;
		font-size: 11px;
		color: var(--muted);
		flex-shrink: 0;
	}

	/* ── Import button ── */
	.import-btn {
		font-family: 'DM Mono', monospace;
		font-size: 11px;
		letter-spacing: 0.08em;
		text-transform: uppercase;
		color: #5bb5a6;
		padding: 6px 12px;
		border-radius: 8px;
		border: 1px solid rgba(91, 181, 166, 0.25);
		background: transparent;
		cursor: pointer;
		transition: background 0.15s;
	}
	.import-btn:hover { background: rgba(91, 181, 166, 0.1); }

	/* ── Modal ── */
	.modal-backdrop {
		position: fixed;
		inset: 0;
		background: rgba(0, 0, 0, 0.6);
		display: flex;
		align-items: center;
		justify-content: center;
		z-index: 100;
	}

	.modal-panel {
		width: 520px;
		max-width: 90vw;
		max-height: 80vh;
		overflow-y: auto;
		border-radius: 14px;
		background: #1a2632;
		border: 1px solid rgba(255, 255, 255, 0.1);
		display: flex;
		flex-direction: column;
		gap: 16px;
		padding: 20px;
	}

	.modal-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
	}

	.modal-header h2 {
		margin: 0;
		font-family: 'Instrument Sans', sans-serif;
		font-size: 16px;
		font-weight: 600;
		color: #eef5f8;
	}

	.modal-close {
		width: 30px;
		height: 30px;
		border-radius: 6px;
		border: 1px solid rgba(255, 255, 255, 0.06);
		background: transparent;
		color: #6b8292;
		cursor: pointer;
		display: flex;
		align-items: center;
		justify-content: center;
		transition: background 0.15s, color 0.15s;
	}
	.modal-close:hover { background: rgba(255, 255, 255, 0.06); color: #c3d3dd; }

	.drop-zone {
		border: 2px dashed rgba(255, 255, 255, 0.12);
		border-radius: 12px;
		padding: 40px 20px;
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 12px;
		color: #6b8292;
		cursor: pointer;
		transition: border-color 0.15s, background 0.15s;
		text-align: center;
		font-family: 'DM Mono', monospace;
		font-size: 12px;
	}
	.drop-zone:hover { border-color: rgba(91, 181, 166, 0.4); background: rgba(91, 181, 166, 0.04); }
	.drop-zone strong { color: #c3d3dd; }

	.file-input-hidden { display: none; }

	.import-status {
		font-family: 'DM Mono', monospace;
		font-size: 12px;
		color: #8fa3b0;
		text-align: center;
		padding: 24px 0;
	}

	.import-error {
		font-family: 'DM Mono', monospace;
		font-size: 11px;
		color: #f2a399;
		padding: 8px 10px;
		border-radius: 8px;
		background: rgba(232, 93, 74, 0.08);
		border: 1px solid rgba(232, 93, 74, 0.2);
	}

	.preview-summary {
		display: flex;
		flex-direction: column;
		gap: 12px;
	}

	.preview-name {
		font-family: 'Instrument Sans', sans-serif;
		font-size: 14px;
		font-weight: 600;
		color: #eef5f8;
	}

	.preview-stats {
		display: flex;
		gap: 12px;
		font-family: 'DM Mono', monospace;
		font-size: 11px;
		color: var(--muted);
	}

	.start-date-field {
		display: flex;
		align-items: center;
		gap: 10px;
	}
	.start-date-field span {
		font-family: 'DM Mono', monospace;
		font-size: 10px;
		letter-spacing: 0.14em;
		text-transform: uppercase;
		color: #8fa3b0;
	}

	.delta-list {
		display: flex;
		flex-direction: column;
		gap: 4px;
		max-height: 200px;
		overflow-y: auto;
	}

	.delta-row {
		display: flex;
		align-items: center;
		gap: 8px;
		padding: 6px 8px;
		border-radius: 6px;
		background: rgba(255, 255, 255, 0.03);
		font-size: 12px;
		color: #a7bac6;
	}

	.delta-action {
		flex-shrink: 0;
		padding: 1px 6px;
		border-radius: 3px;
		font-family: 'DM Mono', monospace;
		font-size: 10px;
		text-transform: uppercase;
		letter-spacing: 0.06em;
	}
	.delta-action.create { background: rgba(91, 181, 166, 0.15); color: #5bb5a6; }
	.delta-action.update { background: rgba(212, 148, 76, 0.15); color: #d4944c; }

	.issue-list {
		display: flex;
		flex-direction: column;
		gap: 4px;
		max-height: 200px;
		overflow-y: auto;
	}

	.issue-row {
		display: flex;
		flex-direction: column;
		gap: 2px;
		padding: 6px 8px;
		border-radius: 6px;
		background: rgba(232, 93, 74, 0.06);
		font-size: 12px;
		color: #f2a399;
	}

	.issue-path {
		font-family: 'DM Mono', monospace;
		font-size: 10px;
		color: #6b8292;
	}

	.import-success {
		font-family: 'Instrument Sans', sans-serif;
		font-size: 14px;
		font-weight: 600;
		color: #5bb5a6;
	}

	.modal-actions {
		display: flex;
		gap: 8px;
	}

	.action-btn {
		padding: 8px 16px;
		border-radius: 8px;
		font-family: 'DM Mono', monospace;
		font-size: 11px;
		letter-spacing: 0.06em;
		cursor: pointer;
		transition: background 0.15s;
	}

	.action-btn.primary {
		background: rgba(91, 181, 166, 0.15);
		border: 1px solid rgba(91, 181, 166, 0.3);
		color: #5bb5a6;
	}
	.action-btn.primary:hover { background: rgba(91, 181, 166, 0.25); }

	.action-btn.ghost {
		background: transparent;
		border: 1px solid rgba(255, 255, 255, 0.08);
		color: #8fa3b0;
	}
	.action-btn.ghost:hover { background: rgba(255, 255, 255, 0.04); }

	/* ── Responsive ── */
	@media (max-width: 768px) {
		.header-bar {
			flex-direction: column;
			align-items: stretch;
			gap: 10px;
		}

		.header-left,
		.header-right {
			justify-content: space-between;
		}

		.timeline-day {
			flex-direction: column;
		}

		.timeline-date {
			flex-direction: row;
			width: auto;
			align-items: center;
			gap: 8px;
			padding: 8px 0 4px 0;
		}

	}
</style>
