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

	/** Which feed's row is currently expanded — null when nothing is expanded. */
	type ExpandedKind = 'routine' | 'training';
	let expandedOccurrenceKey = $state<string | null>(null);
	let expandedKind = $state<ExpandedKind | null>(null);
	let detailNote = $state('');
	/** Actual emitted by the active CardBody; stashed here for schedulePersistDetail. */
	let stagedActual = $state<CardActual | null>(null);
	/** Capture emitted by the active TrainingCardBody; stashed here for scheduleTrainingPersistDetail. */
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

	type CardStatus = 'pending' | 'completed' | 'partial' | 'skipped';

	/** Works for both legacy CardType and TrainingTodayCard — both carry occurrence_key + status. */
	function effectiveStatus(card: { occurrence_key: string; status: CardStatus }): CardStatus {
		return (localStatus[card.occurrence_key] ?? card.status) as CardStatus;
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

	function initializeDetailState(card: CardType) {
		detailNote = card.notes ?? '';
		// Seed from the card's persisted actual so that a notes-only change persists the
		// existing actual correctly (before CardBody has emitted its first onActual).
		stagedActual = card.actual_json;
		variantTaken = card.variant_taken;
	}

	/** Return the payload's variant_options, or [] for payload types that don't carry any. */
	function variantOptionsFor(card: CardType): string[] {
		return 'variant_options' in card.payload_json ? (card.payload_json.variant_options ?? []) : [];
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

	function toggleDetails(card: CardType) {
		// Persist any pending edit for the previously expanded card BEFORE the
		// shared staged state is re-seeded — otherwise the timer fires later and
		// writes the newly expanded card's data onto the old card's log.
		flushPendingPersist();
		if (expandedKind === 'routine' && expandedOccurrenceKey === card.occurrence_key) {
			expandedOccurrenceKey = null;
			expandedKind = null;
			return;
		}
		expandedOccurrenceKey = card.occurrence_key;
		expandedKind = 'routine';
		initializeDetailState(card);
	}

	function initializeTrainingDetailState(card: TrainingTodayCard) {
		detailNote = card.notes ?? '';
		// Seed from the card's persisted capture so that a notes-only change persists the
		// existing capture correctly (before TrainingCardBody has emitted its first onCapture).
		stagedCapture = card.capture;
		variantTaken = card.variant_taken;
	}

	function trainingVariantOptionsFor(card: TrainingTodayCard): string[] {
		return card.variant_options ?? [];
	}

	function toggleTrainingDetails(card: TrainingTodayCard) {
		// Mirrors toggleDetails — see that function's comment for why the flush happens
		// before the shared staged state is re-seeded.
		flushPendingPersist();
		if (expandedKind === 'training' && expandedOccurrenceKey === card.occurrence_key) {
			expandedOccurrenceKey = null;
			expandedKind = null;
			return;
		}
		expandedOccurrenceKey = card.occurrence_key;
		expandedKind = 'training';
		initializeTrainingDetailState(card);
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
	function deriveStatusFromAnswers(
		answers: { item_id: string; checked: boolean; scale: number | null }[],
		itemKinds: Record<string, 'checkbox' | 'tissue_check'>
	): CardStatus {
		if (answers.length === 0) return 'pending';
		const answered = answers.filter((a) =>
			itemKinds[a.item_id] === 'tissue_check' ? a.scale !== null : a.checked
		).length;
		if (answered === answers.length) return 'completed';
		if (answered > 0) return 'partial';
		return 'pending';
	}

	const STATUS_RANK: Record<CardStatus, number> = {
		pending: 0,
		skipped: 0,
		partial: 1,
		completed: 2
	};

	type StrengthActual = Extract<CardActual, { card_type: 'strength_session' }>;

	function setHasData(set: StrengthActual['exercises'][number]['sets'][number]): boolean {
		return set.weight != null || set.reps != null || set.rir != null;
	}

	/**
	 * Derive completion from logged strength sets: every prescribed exercise has
	 * at least one set with data → completed; any data at all → partial.
	 */
	function deriveStatusFromStrength(actual: StrengthActual, prescribedCount: number): CardStatus {
		const loggedPrescribed = new Set(
			actual.exercises
				.filter((ex) => !ex.is_extra && ex.exercise_id && ex.sets.some(setHasData))
				.map((ex) => ex.exercise_id)
		);
		if (prescribedCount > 0 && loggedPrescribed.size >= prescribedCount) return 'completed';
		if (actual.exercises.some((ex) => ex.sets.some(setHasData))) return 'partial';
		return 'pending';
	}

	/** Fire-and-forget persist to backend. No data refresh. */
	async function persistToBackend(
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
	function toggleComplete(card: CardType) {
		const current = effectiveStatus(card);
		const newStatus = current === 'completed' ? 'pending' : 'completed';
		localStatus[card.occurrence_key] = newStatus;
		statusVersion++;

		if (expandedOccurrenceKey === card.occurrence_key) {
			// This explicit persist supersedes any pending debounced one for the card.
			cancelPendingPersist(card.occurrence_key);
			if (card.payload_json.card_type === 'checklist') {
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
					answers: (card.payload_json.items ?? []).map((item) => {
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
			const actual = stagedActual;
			const notes = detailNote.trim() || null;
			if (actual !== null) card.actual_json = actual;
			card.notes = notes;
			card.variant_taken = variantTaken;
			void persistToBackend(card, newStatus, actual, notes, selectedDate, variantTaken);
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

	let saveTimeout: ReturnType<typeof setTimeout> | null = null;
	/** The scheduled debounced persist; key identifies the card it belongs to. */
	let pendingPersist: { key: string; run: () => void } | null = null;

	/** Debounced persist for detail panel changes (notes blur, CardBody onActual, variant tap). */
	function schedulePersistDetail(card: CardType, delay = 500) {
		if (saveTimeout) clearTimeout(saveTimeout);
		// Snapshot everything the persist needs NOW: the shared staged state is
		// re-seeded when another card expands, and selectedDate can change before
		// the timer fires. Status is resolved at fire time so instant local
		// derivation (checklist/strength) is included.
		const actual = stagedActual;
		const notes = detailNote.trim() || null;
		const date = selectedDate;
		const variant = variantTaken;
		const run = () => {
			saveTimeout = null;
			pendingPersist = null;
			if (actual !== null) card.actual_json = actual;
			card.notes = notes;
			card.variant_taken = variant;
			void persistToBackend(card, effectiveStatus(card), actual, notes, date, variant);
		};
		pendingPersist = { key: card.occurrence_key, run };
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
	function onDetailBlur(card: CardType) {
		schedulePersistDetail(card, 400);
	}

	/**
	 * Variant segmented control tap. Selecting "skip" is treated as a status signal (the
	 * user isn't doing the prescribed session at all), so it sets the local status to
	 * skipped — the row checkbox/skip controls remain fully editable afterward. Any other
	 * option only records which variant was taken; it never touches status.
	 */
	function selectVariant(card: CardType, option: string) {
		variantTaken = option;
		if (option === 'skip') {
			localStatus[card.occurrence_key] = 'skipped';
			statusVersion++;
		}
		schedulePersistDetail(card);
	}

	// ── Training feed (v3) — mirrors the legacy routine functions above 1:1. The training
	// PUT endpoint has PARTIAL-KEEP semantics server-side, but this page always sends every
	// field it knows (status/variant_taken/notes/capture) rather than relying on that —
	// PARTIAL-KEEP is a safety net, not the protocol.

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

	/** Row checkbox toggle for a training card — instant local update + background persist. */
	function toggleTrainingComplete(card: TrainingTodayCard) {
		const current = effectiveStatus(card);
		const newStatus = current === 'completed' ? 'pending' : 'completed';
		localStatus[card.occurrence_key] = newStatus;
		statusVersion++;

		if (expandedKind === 'training' && expandedOccurrenceKey === card.occurrence_key) {
			// This explicit persist supersedes any pending debounced one for the card.
			cancelPendingPersist(card.occurrence_key);
			const capture = stagedCapture;
			const notes = detailNote.trim() || null;
			if (capture !== null) card.capture = capture;
			card.notes = notes;
			card.variant_taken = variantTaken;
			void persistTrainingBackend(card, newStatus, capture, notes, selectedDate, variantTaken);
		} else {
			void persistTrainingBackend(card, newStatus);
		}
	}

	/** Row skip button for a training card — instant local update + background persist. */
	function quickTrainingSkip(card: TrainingTodayCard) {
		localStatus[card.occurrence_key] = 'skipped';
		statusVersion++;
		void persistTrainingBackend(card, 'skipped');
	}

	/**
	 * Debounced persist for a training card's detail panel changes (notes blur,
	 * TrainingCardBody onCapture, variant tap). Shares the page's single saveTimeout /
	 * pendingPersist slot with schedulePersistDetail, so scheduling one supersedes the
	 * other — correct, since only one detail panel (routine or training) is ever open.
	 */
	function scheduleTrainingPersistDetail(card: TrainingTodayCard, delay = 500) {
		if (saveTimeout) clearTimeout(saveTimeout);
		const capture = stagedCapture;
		const notes = detailNote.trim() || null;
		const date = selectedDate;
		const variant = variantTaken;
		const run = () => {
			saveTimeout = null;
			pendingPersist = null;
			if (capture !== null) card.capture = capture;
			card.notes = notes;
			card.variant_taken = variant;
			void persistTrainingBackend(card, effectiveStatus(card), capture, notes, date, variant);
		};
		pendingPersist = { key: card.occurrence_key, run };
		saveTimeout = setTimeout(run, delay);
	}

	/** Notes textarea blur for a training card — debounced persist. */
	function onTrainingDetailBlur(card: TrainingTodayCard) {
		scheduleTrainingPersistDetail(card, 400);
	}

	/** Variant segmented control tap for a training card — same skip→status coupling as selectVariant. */
	function selectTrainingVariant(card: TrainingTodayCard, option: string) {
		variantTaken = option;
		if (option === 'skip') {
			localStatus[card.occurrence_key] = 'skipped';
			statusVersion++;
		}
		scheduleTrainingPersistDetail(card);
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
						{@const isExpanded = expandedOccurrenceKey === card.occurrence_key}
						{@const status = effectiveStatus(card)}
						{@const isDone = status === 'completed'}
						{@const isSkipped = status === 'skipped'}
						{@const isPartial = status === 'partial'}
						{@const dt = domainThemeOf(card.payload_json)}
						<div
							class="activity-row"
							class:done={isDone}
							class:skipped={isSkipped}
							class:partial={isPartial}
							class:expanded={isExpanded}
							style={`--dr-color: ${dt.accent}`}
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

								<!-- Domain icon -->
								{#if dt.icon}
									<span class="domain-icon">{dt.icon}</span>
								{/if}

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
									{#key detailRemountToken}
										<CardBody
											{card}
											mode="log"
											onActual={(actual) => {
												stagedActual = actual;
												if (actual.card_type === 'checklist') {
													// Answers are the ground truth; derive status from them directly.
													const status = deriveStatusFromAnswers(
														actual.answers,
														checklistItemKinds(card)
													);
													localStatus[card.occurrence_key] = status;
													statusVersion++;
												} else if (
													actual.card_type === 'strength_session' &&
													card.payload_json.card_type === 'strength_session'
												) {
													// Logged sets are evidence, not the full story — only upgrade,
													// never downgrade an explicitly set completed/skipped status.
													const derived = deriveStatusFromStrength(
														actual,
														(card.payload_json.exercises ?? []).length
													);
													if (STATUS_RANK[derived] > STATUS_RANK[effectiveStatus(card)]) {
														localStatus[card.occurrence_key] = derived;
														statusVersion++;
													}
												}
												schedulePersistDetail(card);
											}}
										/>
									{/key}
									{#if variantOptionsFor(card).length > 0}
										<div class="detail-field variant-field">
											<span>Variant</span>
											<div class="segment-row" role="group" aria-label="Variant taken">
												{#each variantOptionsFor(card) as opt}
													<button
														type="button"
														class="seg-btn"
														class:selected={variantTaken === opt}
														aria-pressed={variantTaken === opt}
														onclick={() => selectVariant(card, opt)}
													>
														{opt}
													</button>
												{/each}
											</div>
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
					{/each}

					{#if trainingCards.length > 0}
						<div class="routine-group-label">{trainingToday?.block_name ?? 'Training'}</div>
						{#each trainingCards as card}
							{@const isExpanded =
								expandedKind === 'training' && expandedOccurrenceKey === card.occurrence_key}
							{@const status = effectiveStatus(card)}
							{@const isDone = status === 'completed'}
							{@const isSkipped = status === 'skipped'}
							{@const isPartial = status === 'partial'}
							{@const theme = trainingCardTheme(card)}
							<div
								class="activity-row"
								class:done={isDone}
								class:skipped={isSkipped}
								class:partial={isPartial}
								class:expanded={isExpanded}
								style={`--dr-color: ${theme.accent}`}
							>
								<div class="row-main">
									<!-- Checkbox -->
									<button
										class="check-toggle"
										class:checked={isDone}
										class:partial-check={isPartial}
										class:skipped-check={isSkipped}
										onclick={() => toggleTrainingComplete(card)}
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

									<!-- Domain icon -->
									{#if theme.icon}
										<span class="domain-icon">{theme.icon}</span>
									{/if}

									<!-- Name + summary -->
									<div class="row-content">
										<span class="row-name">{card.card.name}</span>
										<span class="row-summary">
											{card.bundle_name}{#if card.key_session} · key session{/if}{#if card.measurement_attempt === 'backup'} <span class="backup-test">· Backup test</span>{/if}
										</span>
									</div>

									<!-- Brief metadata -->
									<span class="row-brief">{trainingCardBrief(card)}</span>

									<!-- Actions -->
									<div class="row-actions">
										{#if !isDone}
											<button
												class="skip-btn"
												onclick={() => quickTrainingSkip(card)}
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
											onclick={() => toggleTrainingDetails(card)}
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
										{#if trainingVariantOptionsFor(card).length > 0}
											<div class="detail-field variant-field">
												<span>Variant</span>
												<div class="segment-row" role="group" aria-label="Variant taken">
													{#each trainingVariantOptionsFor(card) as opt}
														<button
															type="button"
															class="seg-btn"
															class:selected={variantTaken === opt}
															aria-pressed={variantTaken === opt}
															onclick={() => selectTrainingVariant(card, opt)}
														>
															{opt}
														</button>
													{/each}
												</div>
											</div>
										{/if}
										<TrainingCardBody
											{card}
											mode="log"
											onCapture={(capture) => {
												stagedCapture = capture;
												scheduleTrainingPersistDetail(card);
											}}
											onRunLink={(patch) => persistRunLink(card, patch)}
										/>
										<label class="detail-field">
											<span>Notes</span>
											<textarea
												bind:value={detailNote}
												rows="2"
												placeholder="Only record what matters."
												onblur={() => onTrainingDetailBlur(card)}
											></textarea>
										</label>
									</div>
								{/if}
							</div>
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

	/* ── Activity row ── */
	.activity-row {
		border-radius: 10px;
		background: rgba(255, 255, 255, 0.025);
		border: 1px solid rgba(255, 255, 255, 0.05);
		border-left: 3px solid var(--dr-color, #5e7282);
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
		border-left-color: var(--dr-color, #5e7282);
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

	.backup-test {
		margin-left: 0.35em;
		color: #8fa3b0;
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

	.domain-icon {
		flex-shrink: 0;
		font-size: 14px;
		line-height: 1;
		opacity: 0.8;
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

	/* ── Variant control ── */
	.variant-field .segment-row {
		display: flex;
		gap: 0;
		border-radius: 8px;
		overflow: hidden;
		border: 1px solid rgba(91, 181, 166, 0.3);
		width: fit-content;
	}

	.variant-field .seg-btn {
		padding: 6px 14px;
		border: none;
		border-right: 1px solid rgba(91, 181, 166, 0.2);
		background: rgba(91, 181, 166, 0.05);
		color: #8fa3b0;
		font: inherit;
		font-size: 12px;
		font-family: 'DM Mono', monospace;
		letter-spacing: 0.04em;
		cursor: pointer;
		transition:
			background 0.15s,
			color 0.15s;
		white-space: nowrap;
	}

	.variant-field .seg-btn:last-child {
		border-right: none;
	}

	.variant-field .seg-btn:hover:not(.selected) {
		background: rgba(91, 181, 166, 0.12);
		color: #c3d3dd;
	}

	.variant-field .seg-btn.selected {
		background: rgba(91, 181, 166, 0.22);
		color: #7be0d0;
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
