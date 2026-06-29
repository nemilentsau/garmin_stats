<script lang="ts">
	import { onMount } from 'svelte';

	import { api, type TodayCardLogUpdate, type TodayResponse } from '$lib/api';
	import { isIsoDateString, localDateIso } from '$lib/date';
	import { cardBrief, slotAccent } from '$lib/routines/card-payloads';
	import CardBody from '$lib/routines/cards/CardBody.svelte';
	import { errorMessage } from '$lib/utils';

	let loading = $state(true);
	let error: string | null = $state(null);
	let selectedDate = $state(localDateIso());
	let today = $state<TodayResponse | null>(null);
	let typeFilter = $state<string | null>(null);
	let slotFilter = $state<string | null>(null);

	type CardType = NonNullable<TodayResponse>['slots'][number]['cards'][number];
	type CardActual = NonNullable<CardType['actual_json']>;

	let expandedOccurrenceKey = $state<string | null>(null);
	let detailNote = $state('');
	/** Actual emitted by the active CardBody; stashed here for debouncedPersistDetail. */
	let stagedActual = $state<CardActual | null>(null);

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
	const routineNames = $derived(
		[...new Set(allCards.map((c) => c.routine_name).filter(Boolean))].sort() as string[]
	);

	type CardStatus = 'pending' | 'completed' | 'partial' | 'skipped';

	function effectiveStatus(card: CardType): CardStatus {
		return (localStatus[card.occurrence_key] ?? card.status) as CardStatus;
	}

	function filteredCards(
		cards: CardType[]
	): CardType[] {
		if (!typeFilter) return cards;
		return cards.filter((c) => c.routine_name === typeFilter);
	}

	function isSlotVisible(slot: string): boolean {
		return !slotFilter || slotFilter === slot;
	}

	type RoutineGroup = { routine: string; cards: CardType[] };

	function groupByRoutine(cards: CardType[]): RoutineGroup[] {
		const groups: RoutineGroup[] = [];
		let current: RoutineGroup | null = null;
		for (const card of cards) {
			const name = card.routine_name ?? 'Other';
			if (!current || current.routine !== name) {
				current = { routine: name, cards: [] };
				groups.push(current);
			}
			current.cards.push(card);
		}
		return groups;
	}

	function initialSelectedDate(): string {
		const fallback = localDateIso();
		const urlDate = new URL(window.location.href).searchParams.get('date');
		return urlDate && isIsoDateString(urlDate) ? urlDate : fallback;
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

	function initializeDetailState(card: CardType) {
		detailNote = card.notes ?? '';
		// Seed from the card's persisted actual so that a notes-only change persists the
		// existing actual correctly (before CardBody has emitted its first onActual).
		stagedActual = card.actual_json;
	}

	function findCardByKey(key: string): CardType | null {
		for (const slot of today?.slots ?? []) {
			const card = slot.cards.find((c) => c.occurrence_key === key);
			if (card) return card;
		}
		return null;
	}

	function toggleDetails(card: CardType) {
		if (expandedOccurrenceKey === card.occurrence_key) {
			expandedOccurrenceKey = null;
			return;
		}
		expandedOccurrenceKey = card.occurrence_key;
		initializeDetailState(card);
	}

	let saveTimeout: ReturnType<typeof setTimeout> | null = null;

	function buildActualJson(_card: CardType): CardActual | null {
		// CardBody emits typed actuals via onActual → stagedActual; return whatever it has stashed.
		return stagedActual;
	}

	/** Derive completion status from a ChecklistActual's answers array. */
	function deriveStatusFromAnswers(answers: { checked: boolean }[]): CardStatus {
		if (answers.length === 0) return 'pending';
		const checked = answers.filter((a) => a.checked).length;
		if (checked === answers.length) return 'completed';
		if (checked > 0) return 'partial';
		return 'pending';
	}

	/** Fire-and-forget persist to backend. No data refresh. */
	async function persistToBackend(
		card: CardType,
		status: CardStatus,
		actual_json?: CardActual | null,
		notes?: string | null
	) {
		error = null;
		try {
			await api.updateTodayCard(selectedDate, card.occurrence_key, {
				card_template_id: card.card_template_id,
				assignment_id: card.assignment_id,
				status,
				// Output union is structurally compatible with the Input union expected by the API.
				actual_json: (actual_json ?? card.actual_json ?? null) as TodayCardLogUpdate['actual_json'],
				notes: notes ?? card.notes ?? null
			});
		} catch (e: unknown) {
			error = errorMessage(e);
		}
	}

	/** Row checkbox toggle — instant local update + background persist. */
	function toggleComplete(card: CardType) {
		const current = effectiveStatus(card);
		const newStatus = current === 'completed' ? 'pending' : 'completed';
		localStatus[card.occurrence_key] = newStatus;
		statusVersion++;

		if (expandedOccurrenceKey === card.occurrence_key) {
			// Detail panel open: persist with current staged actual + notes.
			const actual = buildActualJson(card);
			const notes = detailNote.trim() || null;
			if (actual !== null) card.actual_json = actual;
			card.notes = notes;
			void persistToBackend(card, newStatus, actual, notes);
		} else {
			void persistToBackend(card, newStatus);
		}
	}

	/** Row skip button — instant local update + background persist. */
	function quickSkip(card: CardType) {
		localStatus[card.occurrence_key] = 'skipped';
		statusVersion++;
		void persistToBackend(card, 'skipped');
	}

	/** Debounced persist for detail panel changes (notes blur or CardBody onActual). */
	function debouncedPersistDetail(card: CardType, delay = 500) {
		if (saveTimeout) clearTimeout(saveTimeout);
		saveTimeout = setTimeout(() => {
			const status = effectiveStatus(card);
			const actual = buildActualJson(card);
			const notes = detailNote.trim() || null;
			if (actual !== null) card.actual_json = actual;
			card.notes = notes;
			void persistToBackend(card, status, actual, notes);
		}, delay);
	}

	/** Notes textarea blur — debounced persist. */
	function onDetailBlur(card: CardType) {
		debouncedPersistDetail(card, 400);
	}

	function formatSeconds(totalSeconds: number): string {
		if (totalSeconds < 60) return `${totalSeconds}s`;
		const minutes = Math.floor(totalSeconds / 60);
		const seconds = totalSeconds % 60;
		return seconds === 0 ? `${minutes}m` : `${minutes}m ${seconds}s`;
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
				<a class="routines-link" href="/routines/schedule">Routines</a>
			</div>
		</div>

		{#if error}
			<div class="error-banner">{error}</div>
		{/if}

		<!-- Filter row -->
		<div class="filter-row">
			<select
				class="routine-select"
				value={typeFilter ?? ''}
				onchange={(e) => (typeFilter = e.currentTarget.value || null)}
			>
				<option value="">All routines ({stats.total})</option>
				{#each routineNames as rn}
					<option value={rn}>{rn} ({allCards.filter((c) => c.routine_name === rn).length})</option>
				{/each}
			</select>

			<span class="filter-sep"></span>

			<!-- Slot jump buttons -->
			{#each today?.slots ?? [] as slot}
				{#if slot.cards.length > 0}
					<button
						class="slot-jump"
						class:active={slotFilter === slot.slot}
						style={`--sj-color: ${slotAccent(slot.slot).color}`}
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
				{@const routineGroups = groupByRoutine(cards)}
				{#if cards.length > 0 && isSlotVisible(slot.slot)}
					<div
						class="slot-divider"
						id={`slot-${slot.slot}`}
						style={`--sd-color: ${slotAccent(slot.slot).color}`}
					>
						<span class="slot-label">{slot.label}</span>
						<span class="slot-count">{cards.length}</span>
					</div>

					{#each routineGroups as group}
						{#if routineGroups.length > 1}
							<div class="routine-group-label">{group.routine}</div>
						{/if}
					{#each group.cards as card}
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
									<CardBody
										{card}
										mode="log"
										onActual={(actual) => {
											stagedActual = actual;
											// Derive checklist completion status from the answers array.
											if (actual.card_type === 'checklist') {
												const status = deriveStatusFromAnswers(actual.answers);
												localStatus[card.occurrence_key] = status;
												statusVersion++;
											}
											debouncedPersistDetail(card);
										}}
									/>
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
					{/each}
				{/if}
			{/each}

			<!-- Empty slots -->
			{#each today?.slots ?? [] as slot}
				{#if slot.cards.length === 0 && isSlotVisible(slot.slot)}
					<div
						class="slot-divider empty"
						id={`slot-${slot.slot}`}
						style={`--sd-color: ${slotAccent(slot.slot).color}`}
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
	.routine-select:hover {
		border-color: rgba(255, 255, 255, 0.15);
	}
	.routine-select:focus {
		outline: none;
		border-color: rgba(91, 181, 166, 0.4);
	}
	.routine-select option {
		background: #1a2632;
		color: #c8d6df;
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

	.routine-group-label {
		font-family: 'DM Mono', monospace;
		font-size: 10px;
		letter-spacing: 0.12em;
		text-transform: uppercase;
		color: #6b8292;
		padding: 8px 0 2px;
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

	/* Notes textarea label — detail-field is still used here; card-specific styles live in
	   ChecklistCard.svelte and CardBody.svelte. */
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

	textarea {
		border: 1px solid rgba(255, 255, 255, 0.1);
		background: rgba(8, 15, 24, 0.7);
		color: #eef5f8;
		border-radius: 8px;
		padding: 8px 10px;
		font: inherit;
		font-size: 13px;
		resize: vertical;
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
