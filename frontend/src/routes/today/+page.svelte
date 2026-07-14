<script lang="ts">
	import { onMount, untrack } from 'svelte';

	import {
		api,
		type TodayCardLogUpdate,
		type TodayResponse,
		type TrainingCaptureLog,
		type TrainingLogUpdateRequest,
		type TrainingTodayCard,
		type TrainingTodayResponse
	} from '$lib/api';
	import { isIsoDateString, localDateIso } from '$lib/date';
	import { cardBrief, domainThemeOf, slotAccent } from '$lib/routines/card-payloads';
	import CardBody from '$lib/routines/cards/CardBody.svelte';
	import {
		deriveChecklistStatus,
		effectiveStatus as resolveEffectiveStatus,
		statusForVariant,
		toggledCompletionStatus,
		type CardStatus
	} from '$lib/today-state';
	import TodayActivityRow from '$lib/today/TodayActivityRow.svelte';
	import TodayCardDetails from '$lib/today/TodayCardDetails.svelte';
	import TrainingCardBody from '$lib/training/TrainingCardBody.svelte';
	import { trainingCardBrief, trainingCardTheme } from '$lib/training/training-display';
	import { errorMessage } from '$lib/utils';

	let loading = $state(true);
	let error: string | null = $state(null);
	let selectedDate = $state(localDateIso());
	let today = $state<TodayResponse | null>(null);
	let trainingToday = $state<TrainingTodayResponse | null>(null);
	let typeFilter = $state<string | null>(null);
	let slotFilter = $state<string | null>(null);

	type CardType = NonNullable<TodayResponse>['slots'][number]['cards'][number];
	type CardActual = NonNullable<CardType['actual_json']>;
	type FeedCard =
		| { kind: 'routine'; card: CardType }
		| { kind: 'training'; card: TrainingTodayCard };
	type DetailValue = CardActual | TrainingCaptureLog | null;

	/** Which feed's row is currently expanded — null when nothing is expanded. */
	type ExpandedKind = 'routine' | 'training';
	let expandedOccurrenceKey = $state<string | null>(null);
	let expandedKind = $state<ExpandedKind | null>(null);
	let detailNote = $state('');
	/** Actual emitted by the active CardBody; stashed here for schedulePersistDetail. */
	let stagedActual = $state<CardActual | null>(null);
	/** Capture emitted by the active TrainingCardBody; stashed until the shared detail save runs. */
	let stagedCapture = $state<TrainingCaptureLog | null>(null);
	/** Selected value of the log panel's Variant control, seeded from card.variant_taken. */
	let variantTaken = $state<string | null>(null);
	/** Bumped to remount the expanded CardBody so it re-seeds from card.actual_json. */
	let detailRemountToken = $state(0);

	/** Local status overrides — updated instantly on user action, drives UI. Shared across
	 *  the legacy routine feed and the v3 training feed; their occurrence_key formats never
	 *  collide (routine keys vs. `bundle:card:dNN`), so one map is enough for both. */
	let localStatus = $state<Record<string, string>>({});
	/** Bumped on every local status change to trigger derived re-computation. */
	let statusVersion = $state(0);

	let todayRequestToken = 0;

	const allCards = $derived(today?.slots.flatMap((s) => s.cards) ?? []);
	const allTrainingCards = $derived(trainingToday?.cards ?? []);
	const stats = $derived.by(() => {
		void statusVersion; // track local status changes
		const cards: { occurrence_key: string; status: CardStatus }[] = [...allCards, ...allTrainingCards];
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

	/** Works for both legacy CardType and TrainingTodayCard — both carry occurrence_key + status. */
	function effectiveStatus(card: { occurrence_key: string; status: CardStatus }): CardStatus {
		return resolveEffectiveStatus(card, localStatus);
	}

	function routineFeed(card: CardType): FeedCard {
		return { kind: 'routine', card };
	}

	function trainingFeed(card: TrainingTodayCard): FeedCard {
		return { kind: 'training', card };
	}

	function trainingCardsForSlot(slotName: string): TrainingTodayCard[] {
		return allTrainingCards.filter((c) => c.slot === slotName);
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
		const [response, trainingResponse] = await Promise.all([
			api.getToday(date),
			api.getTrainingToday(date)
		]);
		if (requestToken !== todayRequestToken || date !== selectedDate) return;
		today = response;
		// See the matching comment in routines/schedule/+page.svelte: TrainingTodayResponse
		// embeds the mutually-recursive Predicate union (via V3Card's MeasurementContract),
		// which makes TS treat this call's inferred response type and the TrainingTodayResponse
		// alias as unrelated despite being the same JSON shape. Cast rather than fight it.
		trainingToday = trainingResponse as TrainingTodayResponse;
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
		// Persist any pending detail edit before the board switches away from its
		// date (the persist closure captured its own date snapshot).
		untrack(() => flushPendingPersist());
		expandedOccurrenceKey = null;
		expandedKind = null;
		localStatus = {};
		void loadToday(date, requestToken).catch((e: unknown) => {
			error = errorMessage(e);
		});
	});

	function isExpanded(feed: FeedCard): boolean {
		return expandedKind === feed.kind && expandedOccurrenceKey === feed.card.occurrence_key;
	}

	function variantOptionsFor(feed: FeedCard): string[] {
		if (feed.kind === 'training') return feed.card.variant_options ?? [];
		return 'variant_options' in feed.card.payload_json
			? (feed.card.payload_json.variant_options ?? [])
			: [];
	}

	/** item_id → kind lookup for a checklist card's items; {} for non-checklist payloads. */
	function checklistItemKinds(card: CardType): Record<string, 'checkbox' | 'tissue_check'> {
		if (card.payload_json.card_type !== 'checklist') return {};
		return Object.fromEntries((card.payload_json.items ?? []).map((item) => [item.id, item.kind]));
	}

	function findCardByKey(key: string): CardType | null {
		for (const slot of today?.slots ?? []) {
			const card = slot.cards.find((c) => c.occurrence_key === key);
			if (card) return card;
		}
		return null;
	}

	function toggleDetails(feed: FeedCard) {
		// Persist any pending edit for the previously expanded card BEFORE the
		// shared staged state is re-seeded — otherwise the timer fires later and
		// writes the newly expanded card's data onto the old card's log.
		flushPendingPersist();
		if (isExpanded(feed)) {
			expandedOccurrenceKey = null;
			expandedKind = null;
			return;
		}
		expandedOccurrenceKey = feed.card.occurrence_key;
		expandedKind = feed.kind;
		detailNote = feed.card.notes ?? '';
		variantTaken = feed.card.variant_taken;
		if (feed.kind === 'routine') {
			stagedActual = feed.card.actual_json;
			stagedCapture = null;
		} else {
			stagedCapture = feed.card.capture;
			stagedActual = null;
		}
	}

	/**
	 * Derive completion status from a ChecklistActual's answers array. Answered means:
	 * checkbox items → checked; tissue_check items → a scale value has been recorded
	 * (ChecklistCard's emit() always writes an int 0-3, defaulting to 0, once the card has
	 * been touched — see ChecklistCard's scaleMap comment). itemKinds looks up each
	 * answer's kind from the card's payload so a card mixing both kinds (e.g. tissue
	 * check-in rows + a habitual "core done" checkbox) only reaches 'completed' once every
	 * item — of either kind — has an answer, not just the checkbox ones.
	 */
	/** Fire-and-forget persist to backend. No data refresh. */
	async function persistRoutineBackend(
		card: CardType,
		status: CardStatus,
		actual_json?: CardActual | null,
		notes?: string | null,
		date: string = selectedDate,
		variantTakenValue?: string | null
	) {
		error = null;
		try {
			await api.updateTodayCard(date, card.occurrence_key, {
				card_template_id: card.card_template_id,
				assignment_id: card.assignment_id,
				status,
				// Output union is structurally compatible with the Input union expected by the API.
				actual_json: (actual_json ?? card.actual_json ?? null) as TodayCardLogUpdate['actual_json'],
				notes: notes ?? card.notes ?? null,
				variant_taken: variantTakenValue ?? card.variant_taken ?? null
			});
		} catch (e: unknown) {
			error = errorMessage(e);
		}
	}

	/** Row checkbox toggle — instant local update + background persist. */
	function toggleComplete(feed: FeedCard) {
		const card = feed.card;
		const newStatus = toggledCompletionStatus(effectiveStatus(card));
		localStatus[card.occurrence_key] = newStatus;
		statusVersion++;

		if (isExpanded(feed)) {
			// This explicit persist supersedes any pending debounced one for the card.
			cancelPendingPersist(card.occurrence_key);
			if (feed.kind === 'routine' && feed.card.payload_json.card_type === 'checklist') {
				// The row toggle is authoritative: sync every answer to match so the
				// persisted status and checklist answers can't contradict each other.
				// Build answers from the payload items — stagedActual is null until
				// the first item interaction — keeping any staged item text/scale/flagged.
				// `checked` is forced to match the new row status for every item, including
				// tissue_check items (where it has no independent display meaning — those
				// items are read via scale/flagged, not checked). scale/flagged are never
				// *set* by this row toggle; they're only carried forward from whatever
				// ChecklistCard already staged this session, so a scale/flag tap made just
				// before hitting "mark done" is preserved rather than reset to null.
				const checked = newStatus === 'completed';
				const staged = stagedActual?.card_type === 'checklist' ? stagedActual : null;
				stagedActual = {
					card_type: 'checklist',
					answers: (feed.card.payload_json.items ?? []).map((item) => {
						const existing = staged?.answers.find((a) => a.item_id === item.id);
						return {
							item_id: item.id,
							checked,
							text: existing?.text ?? null,
							scale: existing?.scale ?? null,
							flagged: existing?.flagged ?? false
						};
					})
				};
				detailRemountToken++;
			}
			const detail = feed.kind === 'routine' ? stagedActual : stagedCapture;
			const notes = detailNote.trim() || null;
			applyDetailSnapshot(feed, detail, notes, variantTaken);
			void persistFeed(feed, newStatus, detail, notes, selectedDate, variantTaken);
		} else {
			void persistFeed(feed, newStatus);
		}
	}

	/** Row skip button — instant local update + background persist. */
	function quickSkip(feed: FeedCard) {
		localStatus[feed.card.occurrence_key] = 'skipped';
		statusVersion++;
		void persistFeed(feed, 'skipped');
	}

	let saveTimeout: ReturnType<typeof setTimeout> | null = null;
	/** The scheduled debounced persist; key identifies the card it belongs to. */
	let pendingPersist: { key: string; run: () => void } | null = null;

	/** Debounced persist for detail panel changes (notes blur, CardBody onActual, variant tap). */
	function schedulePersistDetail(feed: FeedCard, delay = 500) {
		if (saveTimeout) clearTimeout(saveTimeout);
		// Snapshot everything the persist needs NOW: the shared staged state is
		// re-seeded when another card expands, and selectedDate can change before
		// the timer fires. Status is resolved at fire time so instant local
		// derivation (checklist/strength) is included.
		const detail = feed.kind === 'routine' ? stagedActual : stagedCapture;
		const notes = detailNote.trim() || null;
		const date = selectedDate;
		const variant = variantTaken;
		const run = () => {
			saveTimeout = null;
			pendingPersist = null;
			applyDetailSnapshot(feed, detail, notes, variant);
			void persistFeed(feed, effectiveStatus(feed.card), detail, notes, date, variant);
		};
		pendingPersist = { key: feed.card.occurrence_key, run };
		saveTimeout = setTimeout(run, delay);
	}

	/** Run the scheduled persist immediately (before staged state is re-seeded). */
	function flushPendingPersist() {
		if (saveTimeout && pendingPersist) {
			clearTimeout(saveTimeout);
			pendingPersist.run();
		}
	}

	/** Drop a scheduled persist that an explicit action for the same card supersedes. */
	function cancelPendingPersist(key: string) {
		if (pendingPersist?.key !== key) return;
		if (saveTimeout) clearTimeout(saveTimeout);
		saveTimeout = null;
		pendingPersist = null;
	}

	/** Notes textarea blur — debounced persist. */
	function onDetailBlur(feed: FeedCard) {
		schedulePersistDetail(feed, 400);
	}

	/**
	 * Variant segmented control tap. Selecting "skip" is treated as a status signal (the
	 * user isn't doing the prescribed session at all), so it sets the local status to
	 * skipped — the row checkbox/skip controls remain fully editable afterward. Any other
	 * option only records which variant was taken; it never touches status.
	 */
	function selectVariant(feed: FeedCard, option: string) {
		variantTaken = option;
		const current = effectiveStatus(feed.card);
		const next = statusForVariant(option, current);
		if (next !== current) {
			localStatus[feed.card.occurrence_key] = next;
			statusVersion++;
		}
		schedulePersistDetail(feed);
	}

	/** Fire-and-forget persist to backend for a training card. No data refresh. */
	async function persistTrainingBackend(
		card: TrainingTodayCard,
		status: CardStatus,
		capture?: TrainingCaptureLog | null,
		notes?: string | null,
		date: string = selectedDate,
		variantTakenValue?: string | null
	) {
		error = null;
		try {
			await api.updateTrainingCard(date, card.occurrence_key, {
				status,
				variant_taken: variantTakenValue ?? card.variant_taken ?? null,
				notes: notes ?? card.notes ?? null,
				// Output shape is structurally compatible with the Input shape the API expects.
				capture: (capture ?? card.capture ?? null) as TrainingLogUpdateRequest['capture']
			});
		} catch (e: unknown) {
			error = errorMessage(e);
		}
	}

	function applyDetailSnapshot(
		feed: FeedCard,
		detail: DetailValue,
		notes: string | null,
		variant: string | null
	) {
		if (feed.kind === 'routine') {
			const actual = detail as CardActual | null;
			if (actual !== null) feed.card.actual_json = actual;
		} else {
			const capture = detail as TrainingCaptureLog | null;
			if (capture !== null) feed.card.capture = capture;
		}
		feed.card.notes = notes;
		feed.card.variant_taken = variant;
	}

	async function persistFeed(
		feed: FeedCard,
		status: CardStatus,
		detail?: DetailValue,
		notes?: string | null,
		date: string = selectedDate,
		variant?: string | null
	) {
		if (feed.kind === 'routine') {
			return persistRoutineBackend(
				feed.card,
				status,
				detail as CardActual | null | undefined,
				notes,
				date,
				variant
			);
		}
		return persistTrainingBackend(
			feed.card,
			status,
			detail as TrainingCaptureLog | null | undefined,
			notes,
			date,
			variant
		);
	}

	/**
	 * Persist a run-link change (candidate pick or detach) for a training card, then refetch
	 * the Today feed. Unlike `persistTrainingBackend`'s optimistic local-merge-and-move-on,
	 * this one awaits and reloads: `associated_activity`/`run_candidates` are backend-computed
	 * (`match_run_to_card`) and the frontend does no matching of its own (display-only rule),
	 * so there is no local value to optimistically merge — and because `run_candidates` is
	 * shared across every run card on the same date, one card's link can change what an
	 * unrelated run card on the same day should now show as its own candidates/association.
	 */
	async function persistRunLink(
		card: TrainingTodayCard,
		patch: { linked_run_id?: string | null; run_link_detached?: boolean | null }
	) {
		error = null;
		try {
			await api.updateTrainingCard(selectedDate, card.occurrence_key, patch);
			todayRequestToken += 1;
			await loadToday(selectedDate, todayRequestToken);
		} catch (e: unknown) {
			error = errorMessage(e);
		}
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
				{#if slot.cards.length > 0 || trainingCardsForSlot(slot.slot).length > 0}
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
		{#if allCards.length === 0 && allTrainingCards.length === 0}
			<div class="empty-board">
				<span>Nothing scheduled for this date.</span>
				<a href="/training/import">No active block — import one</a>
			</div>
		{:else}
		<div class="activity-list">
			{#each today?.slots ?? [] as slot}
				{@const cards = filteredCards(slot.cards)}
				{@const routineGroups = groupByRoutine(cards)}
				{@const trainingCards = trainingCardsForSlot(slot.slot)}
				{#if (cards.length > 0 || trainingCards.length > 0) && isSlotVisible(slot.slot)}
					<div
						class="slot-divider"
						id={`slot-${slot.slot}`}
						style={`--sd-color: ${slotAccent(slot.slot).color}`}
					>
						<span class="slot-label">{slot.label}</span>
						<span class="slot-count">{cards.length + trainingCards.length}</span>
					</div>

					{#each routineGroups as group}
						{#if routineGroups.length > 1}
							<div class="routine-group-label">{group.routine}</div>
						{/if}
						{#each group.cards as card}
							{@const feed = routineFeed(card)}
							{@const theme = domainThemeOf(card.payload_json)}
							<TodayActivityRow
								status={effectiveStatus(card)}
								expanded={isExpanded(feed)}
								accent={theme.accent}
								icon={theme.icon}
								name={card.name}
								summary={card.summary}
								brief={cardBrief(card)}
								tags={card.tags}
								onToggleComplete={() => toggleComplete(feed)}
								onSkip={() => quickSkip(feed)}
								onToggleDetails={() => toggleDetails(feed)}
							>
								<TodayCardDetails
									variantOptions={variantOptionsFor(feed)}
									selectedVariant={variantTaken}
									bind:note={detailNote}
									onSelectVariant={(option) => selectVariant(feed, option)}
									onNoteBlur={() => onDetailBlur(feed)}
								>
									{#key detailRemountToken}
										<CardBody
											{card}
											mode="log"
											onActual={(actual) => {
												stagedActual = actual;
												if (actual.card_type === 'checklist') {
													localStatus[card.occurrence_key] = deriveChecklistStatus(
														actual.answers,
														checklistItemKinds(card)
													);
													statusVersion++;
												}
												schedulePersistDetail(feed);
											}}
										/>
									{/key}
								</TodayCardDetails>
							</TodayActivityRow>
						{/each}
					{/each}

						{#if trainingCards.length > 0}
							<div class="routine-group-label">{trainingToday?.block_name ?? 'Training'}</div>
							{#each trainingCards as card}
								{@const feed = trainingFeed(card)}
								{@const theme = trainingCardTheme(card)}
								<TodayActivityRow
									status={effectiveStatus(card)}
									expanded={isExpanded(feed)}
									accent={theme.accent}
									icon={theme.icon}
									name={card.card.name}
									summary={`${card.bundle_name}${card.key_session ? ' · key session' : ''}`}
									brief={trainingCardBrief(card)}
									backup={card.measurement_attempt === 'backup'}
									onToggleComplete={() => toggleComplete(feed)}
									onSkip={() => quickSkip(feed)}
									onToggleDetails={() => toggleDetails(feed)}
								>
									<TodayCardDetails
										variantOptions={variantOptionsFor(feed)}
										selectedVariant={variantTaken}
										bind:note={detailNote}
										onSelectVariant={(option) => selectVariant(feed, option)}
										onNoteBlur={() => onDetailBlur(feed)}
									>
										<TrainingCardBody
											{card}
											mode="log"
											onCapture={(capture) => {
												stagedCapture = capture;
												schedulePersistDetail(feed);
											}}
											onRunLink={(patch) => persistRunLink(card, patch)}
										/>
									</TodayCardDetails>
								</TodayActivityRow>
							{/each}
					{/if}
				{/if}
			{/each}

			<!-- Empty slots -->
			{#each today?.slots ?? [] as slot}
				{#if slot.cards.length === 0 && trainingCardsForSlot(slot.slot).length === 0 && isSlotVisible(slot.slot)}
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
		{/if}
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

	/* ── Empty board (no routine cards + no training cards for this date) ── */
	.empty-board {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 8px;
		padding: 32px 16px;
		border-radius: 12px;
		border: 1px solid rgba(255, 255, 255, 0.08);
		background: rgba(255, 255, 255, 0.02);
		font-family: 'DM Mono', monospace;
		font-size: 12px;
		color: #8fa3b0;
		text-align: center;
	}

	.empty-board a {
		color: #5bb5a6;
		text-decoration: none;
	}

	.empty-board a:hover {
		text-decoration: underline;
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

	}
</style>
