<script lang="ts">
	import { onMount } from 'svelte';

	import { api, type TodayResponse } from '$lib/api';
	import { isIsoDateString, localDateIso } from '$lib/date';
	import { COLORS, withAlpha } from '$lib/colors';
	import { errorMessage } from '$lib/utils';

	type SlotAccent = {
		color: string;
		shadow: string;
	};

	type TimerPayload = {
		duration_minutes?: number;
		pattern?: string;
		instructions?: string;
		segments?: { label: string; duration_seconds: number }[];
		rating_prompts?: { key: string; label: string; scale_min?: number; scale_max?: number }[];
	};

	type ChecklistPayload = {
		instructions?: string;
		items?: { id: string; label: string; detail?: string }[];
	};

	type ExercisePayload = {
		instructions?: string;
		exercises?: {
			id: string;
			label: string;
			detail?: string;
			reps?: string;
			duration_seconds?: number;
		}[];
	};

	const slotAccent: Record<string, SlotAccent> = {
		morning: { color: COLORS.respiration, shadow: withAlpha(COLORS.respiration, '30') },
		midday: { color: COLORS.spo2, shadow: withAlpha(COLORS.spo2, '30') },
		evening: { color: COLORS.hrv, shadow: withAlpha(COLORS.hrv, '30') },
		anytime: { color: COLORS.stress, shadow: withAlpha(COLORS.stress, '30') }
	};

	const rendererIcon: Record<string, string> = {
		exercise_block: '\u{1F4AA}',
		timer_session: '\u{23F1}',
		checklist_block: '\u{2611}'
	};

	const rendererLabel: Record<string, string> = {
		exercise_block: 'Exercise',
		timer_session: 'Timer',
		checklist_block: 'Checklist'
	};

	let loading = $state(true);
	let error: string | null = $state(null);
	let selectedDate = $state(localDateIso());
	let today = $state<TodayResponse | null>(null);
	let typeFilter = $state<string | null>(null);
	let slotFilter = $state<string | null>(null);

	let expandedOccurrenceKey = $state<string | null>(null);
	let detailDuration = $state<number | null>(null);
	let detailNote = $state('');
	let detailRatings = $state<Record<string, number | null>>({});
	let detailItemStates = $state<Record<string, boolean>>({});

	/** Local status overrides — updated instantly on user action, drives UI. */
	let localStatus = $state<Record<string, string>>({});
	/** Bumped on every local status change to trigger derived re-computation. */
	let statusVersion = $state(0);

	let todayRequestToken = 0;

	const allCards = $derived(today?.slots.flatMap((s) => s.cards) ?? []);
	const stats = $derived.by(() => {
		void statusVersion; // track local status changes
		const cards = allCards;
		let completed = 0, pending = 0, partial = 0, skipped = 0;
		for (const c of cards) {
			const s = effectiveStatus(c);
			if (s === 'completed') completed++;
			else if (s === 'partial') partial++;
			else if (s === 'skipped') skipped++;
			else pending++;
		}
		return { total: cards.length, completed, pending, partial, skipped };
	});
	const rendererTypes = $derived([...new Set(allCards.map((c) => c.renderer))].sort());

	type CardStatus = 'pending' | 'completed' | 'partial' | 'skipped';

	function effectiveStatus(card: NonNullable<TodayResponse>['slots'][number]['cards'][number]): CardStatus {
		return (localStatus[card.occurrence_key] ?? card.status) as CardStatus;
	}

	function filteredCards(
		cards: NonNullable<TodayResponse>['slots'][number]['cards']
	): NonNullable<TodayResponse>['slots'][number]['cards'] {
		if (!typeFilter) return cards;
		return cards.filter((c) => c.renderer === typeFilter);
	}

	function isSlotVisible(slot: string): boolean {
		return !slotFilter || slotFilter === slot;
	}

	function initialSelectedDate(): string {
		const fallback = localDateIso();
		const urlDate = new URL(window.location.href).searchParams.get('date');
		return urlDate && isIsoDateString(urlDate) ? urlDate : fallback;
	}

	function isRecord(value: unknown): value is Record<string, unknown> {
		return typeof value === 'object' && value !== null && !Array.isArray(value);
	}

	function timerPayload(payload: Record<string, unknown>): TimerPayload {
		return payload as TimerPayload;
	}

	function checklistPayload(payload: Record<string, unknown>): ChecklistPayload {
		return payload as ChecklistPayload;
	}

	function exercisePayload(payload: Record<string, unknown>): ExercisePayload {
		return payload as ExercisePayload;
	}

	async function loadToday(date: string, requestToken: number) {
		const response = await api.getToday(date);
		if (requestToken !== todayRequestToken || date !== selectedDate) return;
		today = response;
	}

	async function initializePage() {
		error = null;
		selectedDate = initialSelectedDate();
		todayRequestToken += 1;
		await loadToday(selectedDate, todayRequestToken);
	}

	onMount(() => {
		void initializePage()
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
		todayRequestToken += 1;
		const requestToken = todayRequestToken;
		expandedOccurrenceKey = null;
		localStatus = {};
		void loadToday(date, requestToken).catch((e: unknown) => {
			error = errorMessage(e);
		});
	});

	function initializeDetailState(
		card: NonNullable<TodayResponse>['slots'][number]['cards'][number]
	) {
		const actual = isRecord(card.actual_json) ? card.actual_json : {};
		detailNote = card.notes ?? '';
		detailRatings = {};
		detailItemStates = {};
		detailDuration = null;

		if (card.renderer === 'timer_session') {
			const payload = timerPayload(card.payload_json as Record<string, unknown>);
			detailDuration =
				typeof actual.actual_minutes === 'number'
					? actual.actual_minutes
					: (payload.duration_minutes ?? null);
			if (isRecord(actual.ratings)) {
				for (const [key, value] of Object.entries(actual.ratings)) {
					detailRatings[key] = typeof value === 'number' ? value : null;
				}
			}
			for (const prompt of payload.rating_prompts ?? []) {
				if (!(prompt.key in detailRatings)) {
					detailRatings[prompt.key] = null;
				}
			}
			return;
		}

		if (isRecord(actual.item_states)) {
			for (const [key, value] of Object.entries(actual.item_states)) {
				detailItemStates[key] = value === true;
			}
		}

		const items =
			card.renderer === 'checklist_block'
				? (checklistPayload(card.payload_json as Record<string, unknown>).items ?? [])
				: (exercisePayload(card.payload_json as Record<string, unknown>).exercises ?? []);
		for (const item of items) {
			if (!(item.id in detailItemStates)) {
				detailItemStates[item.id] = false;
			}
		}
	}

	function findCardByKey(key: string): NonNullable<TodayResponse>['slots'][number]['cards'][number] | null {
		for (const slot of today?.slots ?? []) {
			const card = slot.cards.find((c) => c.occurrence_key === key);
			if (card) return card;
		}
		return null;
	}

	function toggleDetails(
		card: NonNullable<TodayResponse>['slots'][number]['cards'][number]
	) {
		if (expandedOccurrenceKey === card.occurrence_key) {
			expandedOccurrenceKey = null;
			return;
		}
		expandedOccurrenceKey = card.occurrence_key;
		initializeDetailState(card);
	}

	let saveTimeout: ReturnType<typeof setTimeout> | null = null;

	function buildActualJson(card: NonNullable<TodayResponse>['slots'][number]['cards'][number]): Record<string, unknown> {
		const actual_json: Record<string, unknown> = {};
		if (card.renderer === 'timer_session') {
			if (detailDuration !== null) actual_json.actual_minutes = detailDuration;
			actual_json.ratings = detailRatings;
		} else {
			actual_json.item_states = detailItemStates;
		}
		return actual_json;
	}

	function deriveStatusFromItems(): CardStatus {
		const values = Object.values(detailItemStates);
		if (values.length === 0) return 'pending';
		const checked = values.filter(Boolean).length;
		if (checked === values.length) return 'completed';
		if (checked > 0) return 'partial';
		return 'pending';
	}

	/** Fire-and-forget persist to backend. No data refresh. */
	async function persistToBackend(
		card: NonNullable<TodayResponse>['slots'][number]['cards'][number],
		status: 'pending' | 'completed' | 'partial' | 'skipped',
		actual_json?: Record<string, unknown>,
		notes?: string | null
	) {
		error = null;
		try {
			await api.updateTodayCard(selectedDate, card.occurrence_key, {
				card_template_id: card.card_template_id,
				assignment_id: card.assignment_id,
				status,
				actual_json: actual_json ?? (isRecord(card.actual_json) ? card.actual_json : {}),
				notes: notes ?? card.notes ?? null
			});
			} catch (e: unknown) {
			error = errorMessage(e);
		}
	}

	/** Row checkbox toggle — instant local update + background persist. */
	function toggleComplete(
		card: NonNullable<TodayResponse>['slots'][number]['cards'][number]
	) {
		const current = effectiveStatus(card);
		const newStatus = current === 'completed' ? 'pending' : 'completed';
		localStatus[card.occurrence_key] = newStatus;
		statusVersion++;

		// Sync sub-checkboxes if detail panel is open for this card
		if (expandedOccurrenceKey === card.occurrence_key && card.renderer !== 'timer_session') {
			const setAll = newStatus === 'completed';
			for (const key of Object.keys(detailItemStates)) {
				detailItemStates[key] = setAll;
			}
			void persistToBackend(card, newStatus, buildActualJson(card), detailNote.trim() || null);
		} else {
			void persistToBackend(card, newStatus);
		}
	}

	/** Row skip button — instant local update + background persist. */
	function quickSkip(
		card: NonNullable<TodayResponse>['slots'][number]['cards'][number]
	) {
		localStatus[card.occurrence_key] = 'skipped';
		statusVersion++;
		void persistToBackend(card, 'skipped');
	}

	/** Detail checkbox toggle — update local state + derived status instantly, debounced persist. */
	function onDetailCheckboxChange(
		card: NonNullable<TodayResponse>['slots'][number]['cards'][number]
	) {
		const derived = deriveStatusFromItems();
		localStatus[card.occurrence_key] = derived;
		statusVersion++;
		debouncedPersistDetail(card);
	}

	/** Debounced persist for detail panel changes. */
	function debouncedPersistDetail(
		card: NonNullable<TodayResponse>['slots'][number]['cards'][number],
		delay = 500
	) {
		if (saveTimeout) clearTimeout(saveTimeout);
		saveTimeout = setTimeout(() => {
			const status = effectiveStatus(card);
			void persistToBackend(card, status, buildActualJson(card), detailNote.trim() || null);
		}, delay);
	}

	/** Notes/duration blur — debounced persist. */
	function onDetailBlur(
		card: NonNullable<TodayResponse>['slots'][number]['cards'][number]
	) {
		debouncedPersistDetail(card, 400);
	}

	function formatSeconds(totalSeconds: number): string {
		if (totalSeconds < 60) return `${totalSeconds}s`;
		const minutes = Math.floor(totalSeconds / 60);
		const seconds = totalSeconds % 60;
		return seconds === 0 ? `${minutes}m` : `${minutes}m ${seconds}s`;
	}

	function cardBrief(
		card: NonNullable<TodayResponse>['slots'][number]['cards'][number]
	): string {
		if (card.renderer === 'timer_session') {
			const p = timerPayload(card.payload_json as Record<string, unknown>);
			return p.duration_minutes ? `${p.duration_minutes} min` : '';
		}
		if (card.renderer === 'exercise_block') {
			const p = exercisePayload(card.payload_json as Record<string, unknown>);
			return p.exercises?.length ? `${p.exercises.length} exercises` : '';
		}
		const p = checklistPayload(card.payload_json as Record<string, unknown>);
		return p.items?.length ? `${p.items.length} items` : '';
	}
</script>

<svelte:head>
	<title>Today - Garmin Stats</title>
</svelte:head>

{#if loading}
	<section class="loading-shell">
		<div class="loading-card">Compiling today from live routines...</div>
	</section>
{:else}
	<section class="today-shell">
		<!-- Compact header bar -->
		<div class="header-bar">
			<div class="header-left">
				<h1>Today</h1>
				<input type="date" class="date-input" bind:value={selectedDate} />
			</div>
			<div class="header-right">
				<div class="progress-info">
					<span class="progress-text">
						<strong>{stats.completed}</strong> / {stats.total} done
					</span>
					<div class="progress-bar">
						{#if stats.total > 0}
							<div
								class="progress-fill completed"
								style={`width: ${(stats.completed / stats.total) * 100}%`}
							></div>
							<div
								class="progress-fill partial"
								style={`width: ${(stats.partial / stats.total) * 100}%`}
							></div>
							<div
								class="progress-fill skipped"
								style={`width: ${(stats.skipped / stats.total) * 100}%`}
							></div>
						{/if}
					</div>
				</div>
				<a class="routines-link" href="/routines/creation">Routines</a>
			</div>
		</div>

		{#if error}
			<div class="error-banner">{error}</div>
		{/if}

		<!-- Filter chips -->
		<div class="filter-row">
			<button
				class="filter-chip"
				class:active={typeFilter === null}
				onclick={() => (typeFilter = null)}
			>
				All <span class="chip-count">{stats.total}</span>
			</button>
			{#each rendererTypes as rt}
				<button
					class="filter-chip"
					class:active={typeFilter === rt}
					onclick={() => (typeFilter = typeFilter === rt ? null : rt)}
				>
					<span class="chip-icon">{rendererIcon[rt] ?? ''}</span>
					{rendererLabel[rt] ?? rt}
					<span class="chip-count">{allCards.filter((c) => c.renderer === rt).length}</span>
				</button>
			{/each}

			<span class="filter-sep"></span>

			<!-- Slot jump buttons -->
			{#each today?.slots ?? [] as slot}
				{#if slot.cards.length > 0}
					<button
						class="slot-jump"
						class:active={slotFilter === slot.slot}
						style={`--sj-color: ${slotAccent[slot.slot]?.color ?? '#8a9baa'}`}
						onclick={() => (slotFilter = slotFilter === slot.slot ? null : slot.slot)}
					>
						{slot.label}
					</button>
				{/if}
			{/each}
		</div>

		<!-- Activity list -->
		<div class="activity-list">
			{#each today?.slots ?? [] as slot}
				{@const cards = filteredCards(slot.cards)}
				{#if cards.length > 0 && isSlotVisible(slot.slot)}
					<div
						class="slot-divider"
						id={`slot-${slot.slot}`}
						style={`--sd-color: ${slotAccent[slot.slot]?.color ?? '#8a9baa'}`}
					>
						<span class="slot-label">{slot.label}</span>
						<span class="slot-count">{cards.length}</span>
					</div>

					{#each cards as card}
						{@const isExpanded = expandedOccurrenceKey === card.occurrence_key}
						{@const status = effectiveStatus(card)}
						{@const isDone = status === 'completed'}
						{@const isSkipped = status === 'skipped'}
						{@const isPartial = status === 'partial'}
						<div
							class="activity-row"
							class:done={isDone}
							class:skipped={isSkipped}
							class:partial={isPartial}
							class:expanded={isExpanded}
						>
							<div class="row-main">
								<!-- Checkbox -->
								<button
									class="check-toggle"
									class:checked={isDone}
									class:partial-check={isPartial}
									class:skipped-check={isSkipped}
									onclick={() => toggleComplete(card)}
									title={isDone ? 'Mark pending' : 'Mark done'}
								>
									{#if isDone}
										<svg viewBox="0 0 16 16" width="14" height="14" fill="none">
											<path
												d="M3.5 8.5L6.5 11.5L12.5 4.5"
												stroke="currentColor"
												stroke-width="2"
												stroke-linecap="round"
												stroke-linejoin="round"
											/>
										</svg>
									{:else if isSkipped}
										<svg viewBox="0 0 16 16" width="12" height="12" fill="none">
											<path
												d="M4 4L12 12M12 4L4 12"
												stroke="currentColor"
												stroke-width="2"
												stroke-linecap="round"
											/>
										</svg>
									{:else if isPartial}
										<svg viewBox="0 0 16 16" width="12" height="12" fill="none">
											<path
												d="M3 8H13"
												stroke="currentColor"
												stroke-width="2"
												stroke-linecap="round"
											/>
										</svg>
									{/if}
								</button>

								<!-- Type icon -->
								<span class="type-icon" title={rendererLabel[card.renderer] ?? card.renderer}>
									{rendererIcon[card.renderer] ?? ''}
								</span>

								<!-- Name + summary -->
								<div class="row-content">
									<span class="row-name">{card.name}</span>
									{#if card.summary}
										<span class="row-summary">{card.summary}</span>
									{/if}
								</div>

								<!-- Brief metadata -->
								<span class="row-brief">{cardBrief(card)}</span>

								<!-- Tags (compact, first 2 only) -->
								<div class="row-tags">
									{#each card.tags.slice(0, 2) as tag}
										<span class="mini-tag">{tag}</span>
									{/each}
								</div>

								<!-- Actions -->
								<div class="row-actions">
									{#if !isDone}
										<button
											class="skip-btn"
											onclick={() => quickSkip(card)}
											title="Skip"
										>
											<svg viewBox="0 0 16 16" width="14" height="14" fill="none">
												<path
													d="M4 4L12 12M12 4L4 12"
													stroke="currentColor"
													stroke-width="1.5"
													stroke-linecap="round"
												/>
											</svg>
										</button>
									{/if}
									<button
										class="expand-btn"
										class:active={isExpanded}
										onclick={() => toggleDetails(card)}
										title="Details"
									>
										<svg
											viewBox="0 0 16 16"
											width="14"
											height="14"
											fill="none"
											style={`transform: rotate(${isExpanded ? 180 : 0}deg); transition: transform 0.2s`}
										>
											<path
												d="M4 6L8 10L12 6"
												stroke="currentColor"
												stroke-width="1.5"
												stroke-linecap="round"
												stroke-linejoin="round"
											/>
										</svg>
									</button>
								</div>
							</div>

							<!-- Expanded detail panel -->
							{#if isExpanded}
								<div class="detail-panel">
									{#if card.renderer === 'timer_session'}
										{@const payload = timerPayload(
											card.payload_json as Record<string, unknown>
										)}
										{#if payload.instructions}
											<p class="detail-copy">{payload.instructions}</p>
										{/if}
										{#if (payload.segments?.length ?? 0) > 0}
											<div class="detail-list">
												{#each payload.segments ?? [] as segment}
													<div class="detail-row">
														<span>{segment.label}</span>
														<strong>{formatSeconds(segment.duration_seconds)}</strong>
													</div>
												{/each}
											</div>
										{/if}
										<label class="detail-field">
											<span>Actual minutes</span>
											<input type="number" bind:value={detailDuration} min="0" onblur={() => onDetailBlur(card)} />
										</label>
										{#if (payload.rating_prompts?.length ?? 0) > 0}
											<div class="ratings-grid">
												{#each payload.rating_prompts ?? [] as prompt}
													<label class="detail-field">
														<span>{prompt.label}</span>
														<input
															type="number"
															bind:value={detailRatings[prompt.key]}
															min={prompt.scale_min ?? 1}
															max={prompt.scale_max ?? 5}
															onblur={() => onDetailBlur(card)}
														/>
													</label>
												{/each}
											</div>
										{/if}
									{:else if card.renderer === 'checklist_block'}
										{@const payload = checklistPayload(
											card.payload_json as Record<string, unknown>
										)}
										{#if payload.instructions}
											<p class="detail-copy">{payload.instructions}</p>
										{/if}
										<div class="checklist">
											{#each payload.items ?? [] as item}
												<label class="check-item">
													<input
														type="checkbox"
														bind:checked={detailItemStates[item.id]}
														onchange={() => onDetailCheckboxChange(card)}
													/>
													<div>
														<strong>{item.label}</strong>
														{#if item.detail}
															<small>{item.detail}</small>
														{/if}
													</div>
												</label>
											{/each}
										</div>
									{:else}
										{@const payload = exercisePayload(
											card.payload_json as Record<string, unknown>
										)}
										{#if payload.instructions}
											<p class="detail-copy">{payload.instructions}</p>
										{/if}
										<div class="checklist">
											{#each payload.exercises ?? [] as exercise}
												<label class="check-item">
													<input
														type="checkbox"
														bind:checked={detailItemStates[exercise.id]}
														onchange={() => onDetailCheckboxChange(card)}
													/>
													<div>
														<strong>{exercise.label}</strong>
														<small>
															{exercise.detail ?? exercise.reps ?? ''}
															{#if exercise.duration_seconds}
																{exercise.detail || exercise.reps ? ' \u00B7 ' : ''}{formatSeconds(exercise.duration_seconds)}
															{/if}
														</small>
													</div>
												</label>
											{/each}
										</div>
									{/if}

									<label class="detail-field">
										<span>Notes</span>
										<textarea
											bind:value={detailNote}
											rows="2"
											placeholder="Only record what matters."
											onblur={() => onDetailBlur(card)}
										></textarea>
									</label>
								</div>
							{/if}
						</div>
					{/each}
				{/if}
			{/each}

			<!-- Empty slots -->
			{#each today?.slots ?? [] as slot}
				{#if slot.cards.length === 0 && isSlotVisible(slot.slot)}
					<div
						class="slot-divider empty"
						id={`slot-${slot.slot}`}
						style={`--sd-color: ${slotAccent[slot.slot]?.color ?? '#8a9baa'}`}
					>
						<span class="slot-label">{slot.label}</span>
						<span class="slot-empty-text">nothing scheduled</span>
					</div>
				{/if}
			{/each}
		</div>
	</section>
{/if}

<style>
	.today-shell {
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
	.error-banner {
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

	.date-input {
		border: 1px solid rgba(255, 255, 255, 0.1);
		background: rgba(8, 15, 24, 0.7);
		color: #c3d3dd;
		border-radius: 8px;
		padding: 6px 10px;
		font-family: 'DM Mono', monospace;
		font-size: 12px;
	}

	.header-right {
		display: flex;
		align-items: center;
		gap: 16px;
	}

	.progress-info {
		display: flex;
		align-items: center;
		gap: 10px;
	}

	.progress-text {
		font-family: 'DM Mono', monospace;
		font-size: 12px;
		color: var(--muted);
		white-space: nowrap;
	}

	.progress-text strong {
		color: #eef5f8;
		font-size: 14px;
	}

	.progress-bar {
		width: 120px;
		height: 6px;
		border-radius: 3px;
		background: rgba(255, 255, 255, 0.06);
		display: flex;
		overflow: hidden;
	}

	.progress-fill {
		height: 100%;
		transition: width 0.3s ease;
	}

	.progress-fill.completed {
		background: #5bb5a6;
	}
	.progress-fill.partial {
		background: #d4944c;
	}
	.progress-fill.skipped {
		background: #e85d4a;
	}

	.routines-link {
		font-family: 'DM Mono', monospace;
		font-size: 11px;
		letter-spacing: 0.08em;
		text-transform: uppercase;
		color: #5bb5a6;
		text-decoration: none;
		padding: 6px 12px;
		border-radius: 8px;
		border: 1px solid rgba(91, 181, 166, 0.25);
		transition: background 0.15s;
	}

	.routines-link:hover {
		background: rgba(91, 181, 166, 0.1);
	}

	/* ── Filter chips ── */
	.filter-row {
		display: flex;
		align-items: center;
		gap: 6px;
		flex-wrap: wrap;
	}

	.filter-chip {
		display: inline-flex;
		align-items: center;
		gap: 6px;
		padding: 5px 12px;
		border-radius: 8px;
		border: 1px solid rgba(255, 255, 255, 0.08);
		background: transparent;
		color: #8fa3b0;
		font-family: 'DM Mono', monospace;
		font-size: 11px;
		letter-spacing: 0.04em;
		cursor: pointer;
		transition:
			background 0.15s,
			border-color 0.15s,
			color 0.15s;
	}

	.filter-chip:hover {
		background: rgba(255, 255, 255, 0.04);
	}

	.filter-chip.active {
		background: rgba(91, 181, 166, 0.12);
		border-color: rgba(91, 181, 166, 0.3);
		color: #7be0d0;
	}

	.chip-count {
		font-weight: 700;
		opacity: 0.7;
	}

	.chip-icon {
		font-size: 13px;
	}

	.filter-sep {
		width: 1px;
		height: 20px;
		background: rgba(255, 255, 255, 0.08);
		margin: 0 4px;
	}

	.slot-jump {
		padding: 4px 10px;
		border-radius: 6px;
		border: 1px solid color-mix(in srgb, var(--sj-color) 30%, transparent);
		background: transparent;
		color: var(--sj-color);
		font-family: 'DM Mono', monospace;
		font-size: 10px;
		letter-spacing: 0.1em;
		text-transform: uppercase;
		cursor: pointer;
		transition: background 0.15s;
	}

	.slot-jump:hover {
		background: color-mix(in srgb, var(--sj-color) 10%, transparent);
	}

	.slot-jump.active {
		background: color-mix(in srgb, var(--sj-color) 15%, transparent);
		border-color: color-mix(in srgb, var(--sj-color) 50%, transparent);
	}

	/* ── Activity list ── */
	.activity-list {
		display: flex;
		flex-direction: column;
		gap: 2px;
	}

	.slot-divider {
		display: flex;
		align-items: center;
		gap: 8px;
		padding: 10px 0 6px;
		margin-top: 8px;
		border-bottom: 1px solid rgba(255, 255, 255, 0.06);
	}

	.slot-divider:first-child {
		margin-top: 0;
	}

	.slot-divider::before {
		content: '';
		width: 3px;
		height: 14px;
		border-radius: 2px;
		background: var(--sd-color);
	}

	.slot-label {
		font-family: 'DM Mono', monospace;
		font-size: 11px;
		letter-spacing: 0.14em;
		text-transform: uppercase;
		color: var(--sd-color);
		font-weight: 600;
	}

	.slot-count {
		font-family: 'DM Mono', monospace;
		font-size: 11px;
		color: var(--muted);
	}

	.slot-empty-text {
		font-family: 'DM Mono', monospace;
		font-size: 11px;
		color: rgba(127, 149, 166, 0.5);
		font-style: italic;
	}

	.slot-divider.empty {
		opacity: 0.5;
	}

	/* ── Activity row ── */
	.activity-row {
		border-radius: 10px;
		background: rgba(255, 255, 255, 0.025);
		border: 1px solid rgba(255, 255, 255, 0.05);
		transition:
			background 0.15s,
			opacity 0.2s;
	}

	.activity-row:hover {
		background: rgba(255, 255, 255, 0.045);
	}

	.activity-row.done {
		opacity: 0.45;
	}

	.activity-row.done:hover {
		opacity: 0.7;
	}

	.activity-row.skipped {
		opacity: 0.35;
	}

	.activity-row.skipped:hover {
		opacity: 0.6;
	}

	.activity-row.partial {
		opacity: 0.6;
	}

	.activity-row.expanded {
		opacity: 1;
		background: rgba(255, 255, 255, 0.04);
		border-color: rgba(255, 255, 255, 0.1);
	}

	.row-main {
		display: flex;
		align-items: center;
		gap: 10px;
		padding: 10px 14px;
		min-height: 48px;
	}

	/* ── Checkbox toggle ── */
	.check-toggle {
		flex-shrink: 0;
		width: 24px;
		height: 24px;
		border-radius: 6px;
		border: 2px solid rgba(255, 255, 255, 0.15);
		background: transparent;
		color: transparent;
		cursor: pointer;
		display: flex;
		align-items: center;
		justify-content: center;
		transition:
			border-color 0.15s,
			background 0.15s,
			color 0.15s;
	}

	.check-toggle:hover {
		border-color: rgba(91, 181, 166, 0.5);
	}

	.check-toggle.checked {
		background: rgba(91, 181, 166, 0.2);
		border-color: #5bb5a6;
		color: #7be0d0;
	}

	.check-toggle.partial-check {
		background: rgba(212, 148, 76, 0.15);
		border-color: #d4944c;
		color: #f3bf81;
	}

	.check-toggle.skipped-check {
		background: rgba(232, 93, 74, 0.12);
		border-color: rgba(232, 93, 74, 0.4);
		color: #f2a399;
	}

	.type-icon {
		flex-shrink: 0;
		width: 22px;
		text-align: center;
		font-size: 15px;
		filter: grayscale(0.3);
	}

	.row-content {
		flex: 1;
		min-width: 0;
		display: flex;
		flex-direction: column;
		gap: 1px;
	}

	.row-name {
		font-family: 'Instrument Sans', sans-serif;
		font-size: 14px;
		font-weight: 600;
		color: #eef5f8;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}

	.activity-row.done .row-name {
		text-decoration: line-through;
		text-decoration-color: rgba(91, 181, 166, 0.5);
	}

	.activity-row.skipped .row-name {
		text-decoration: line-through;
		text-decoration-color: rgba(232, 93, 74, 0.4);
	}

	.row-summary {
		font-size: 12px;
		color: #8fa3b0;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}

	.row-brief {
		flex-shrink: 0;
		font-family: 'DM Mono', monospace;
		font-size: 11px;
		color: #6b8292;
	}

	.row-tags {
		display: flex;
		gap: 4px;
		flex-shrink: 0;
	}

	.mini-tag {
		padding: 2px 7px;
		border-radius: 4px;
		background: rgba(255, 255, 255, 0.05);
		font-family: 'DM Mono', monospace;
		font-size: 10px;
		color: #8fa3b0;
	}

	.row-actions {
		display: flex;
		align-items: center;
		gap: 4px;
		flex-shrink: 0;
	}

	.skip-btn,
	.expand-btn {
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
		transition:
			background 0.15s,
			color 0.15s;
	}

	.skip-btn:hover {
		background: rgba(232, 93, 74, 0.1);
		color: #f2a399;
	}

	.expand-btn:hover,
	.expand-btn.active {
		background: rgba(255, 255, 255, 0.06);
		color: #c3d3dd;
	}

	/* ── Detail panel ── */
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

	.detail-list,
	.checklist {
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

	.detail-field {
		display: flex;
		flex-direction: column;
		gap: 6px;
	}

	.detail-field span {
		font-family: 'DM Mono', monospace;
		font-size: 10px;
		letter-spacing: 0.14em;
		text-transform: uppercase;
		color: #8fa3b0;
	}

	input,
	textarea {
		border: 1px solid rgba(255, 255, 255, 0.1);
		background: rgba(8, 15, 24, 0.7);
		color: #eef5f8;
		border-radius: 8px;
		padding: 8px 10px;
		font: inherit;
		font-size: 13px;
	}

	textarea {
		resize: vertical;
	}

	.ratings-grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
		gap: 8px;
	}

	.check-item {
		display: grid;
		grid-template-columns: auto minmax(0, 1fr);
		gap: 10px;
		padding: 8px 10px;
		border-radius: 8px;
		background: rgba(255, 255, 255, 0.03);
		font-size: 13px;
	}

	.check-item strong {
		font-size: 13px;
	}

	.check-item small {
		display: block;
		margin-top: 2px;
		color: #6b8292;
		font-size: 11px;
	}

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

		.row-main {
			flex-wrap: wrap;
			gap: 8px;
		}

		.row-tags {
			display: none;
		}

		.row-brief {
			display: none;
		}

	}
</style>
