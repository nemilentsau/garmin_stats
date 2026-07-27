<script lang="ts">
	import { onMount, untrack } from 'svelte';

	import {
		api,
		type TrainingCaptureLog,
		type TrainingLogUpdateRequest,
		type TrainingTodayCard,
		type TrainingTodayResponse
	} from '$lib/api';
	import { fmtFullDate, isIsoDateString, localDateIso, parseIsoDate } from '$lib/date';
	import {
		completionStatusAfterClick,
		createStatusPersistQueue,
		effectiveStatus as resolveEffectiveStatus,
		loadedMutationDate,
		statusForVariant,
		type CardStatus
	} from '$lib/today-state';
	import TodayActivityRow from '$lib/today/TodayActivityRow.svelte';
	import TodayCardDetails from '$lib/today/TodayCardDetails.svelte';
	import TrainingCardBody from '$lib/training/TrainingCardBody.svelte';
	import {
		SLOT_LABELS,
		SLOT_ORDER,
		slotAccent,
		trainingCardBrief,
		trainingCardTheme,
		type SlotName
	} from '$lib/training/training-display';
	import { errorMessage } from '$lib/utils';

	let loading = $state(true);
	let error: string | null = $state(null);
	let selectedDate = $state(localDateIso());
	let loadedDate = $state<string | null>(null);
	let requestedDate = $state<string | null>(null);
	let trainingToday = $state<TrainingTodayResponse | null>(null);
	let slotFilter = $state<SlotName | null>(null);
	let expandedOccurrenceKey = $state<string | null>(null);
	let detailNote = $state('');
	let stagedCapture = $state<TrainingCaptureLog | null>(null);
	let variantTaken = $state<string | null>(null);
	let localStatus = $state<Record<string, string>>({});
	let statusVersion = $state(0);
	const statusPersistQueue = createStatusPersistQueue();
	let todayRequestToken = 0;
	let mounted = $state(false);

	const allCards = $derived(trainingToday?.cards ?? []);
	const stats = $derived.by(() => {
		void statusVersion;
		let completed = 0;
		let pending = 0;
		let partial = 0;
		let skipped = 0;
		for (const card of allCards) {
			const status = effectiveStatus(card);
			if (status === 'completed') completed++;
			else if (status === 'partial') partial++;
			else if (status === 'skipped') skipped++;
			else pending++;
		}
		return { total: allCards.length, completed, pending, partial, skipped };
	});

	function effectiveStatus(card: TrainingTodayCard): CardStatus {
		return resolveEffectiveStatus(card, localStatus);
	}

	function cardsForSlot(slot: SlotName): TrainingTodayCard[] {
		return allCards.filter((card) => card.slot === slot);
	}

	function initialSelectedDate(): string {
		const fallback = localDateIso();
		const urlDate = new URL(window.location.href).searchParams.get('date');
		return urlDate && isIsoDateString(urlDate) ? urlDate : fallback;
	}

	async function reloadToday(date: string): Promise<void> {
		const requestToken = ++todayRequestToken;
		requestedDate = date;
		loadedDate = null;
		trainingToday = null;
		loading = true;
		error = null;
		try {
			const response = await api.getTrainingToday(date);
			if (requestToken !== todayRequestToken || date !== selectedDate) return;
			trainingToday = response as TrainingTodayResponse;
			loadedDate = date;
		} catch (cause: unknown) {
			if (requestToken === todayRequestToken && date === selectedDate) {
				error = errorMessage(cause);
			}
		} finally {
			if (requestToken === todayRequestToken && date === selectedDate) {
				loading = false;
			}
		}
	}

	function mutationDate(): string | null {
		return loadedMutationDate(selectedDate, loadedDate);
	}

	onMount(() => {
		selectedDate = initialSelectedDate();
		mounted = true;
		void reloadToday(selectedDate);
	});

	$effect(() => {
		if (!mounted || selectedDate === loadedDate || selectedDate === requestedDate) return;
		// Clearing the native date input (or an incomplete in-progress edit) yields '' /
		// a non-ISO value — ignore it and keep whatever's currently on screen rather than
		// tearing down state for a date that can't be fetched (matches the guard already
		// in `createDateLoader`, `$lib/realtime-page.ts`).
		if (!isIsoDateString(selectedDate)) return;
		const date = selectedDate;
		untrack(() => flushPendingPersist());
		expandedOccurrenceKey = null;
		localStatus = {};
		void reloadToday(date);
	});

	function toggleDetails(card: TrainingTodayCard): void {
		flushPendingPersist();
		if (expandedOccurrenceKey === card.occurrence_key) {
			expandedOccurrenceKey = null;
			return;
		}
		expandedOccurrenceKey = card.occurrence_key;
		detailNote = card.notes ?? '';
		stagedCapture = card.capture;
		variantTaken = card.variant_taken;
	}

	async function persistCard(
		card: TrainingTodayCard,
		status: CardStatus | undefined,
		date: string,
		capture: TrainingCaptureLog | null = card.capture,
		notes: string | null = card.notes,
		variant: string | null = card.variant_taken
	): Promise<boolean> {
		error = null;
		try {
			const payload: TrainingLogUpdateRequest = {
				variant_taken: variant,
				notes,
				capture: capture as TrainingLogUpdateRequest['capture']
			};
			if (status !== undefined) payload.status = status;
			await api.updateTrainingCard(date, card.occurrence_key, payload);
			return true;
		} catch (cause: unknown) {
			if (selectedDate === date) error = errorMessage(cause);
			return false;
		}
	}

	function trackOptimisticStatus(
		card: TrainingTodayCard,
		attempted: CardStatus,
		previous: CardStatus,
		date: string,
		persist: () => Promise<boolean>
	): void {
		void statusPersistQueue.enqueue({
			key: `${date}:${card.occurrence_key}`,
			attempted,
			initialConfirmed: previous,
			persist,
			isCurrent: () => selectedDate === date && localStatus[card.occurrence_key] === attempted,
			rollback: (confirmed) => {
				localStatus[card.occurrence_key] = confirmed;
				statusVersion++;
			}
		});
	}

	function applyDetailSnapshot(
		card: TrainingTodayCard,
		capture: TrainingCaptureLog | null,
		notes: string | null,
		variant: string | null
	): void {
		if (capture !== null) card.capture = capture;
		card.notes = notes;
		card.variant_taken = variant;
	}

	function toggleComplete(card: TrainingTodayCard): void {
		const date = mutationDate();
		if (date === null) return;
		const previous = effectiveStatus(card);
		const submittingTrackedRun =
			card.execution.source === 'tracked_run' && previous === 'completed';
		const next = completionStatusAfterClick(previous, card.execution.source);
		const persistCompletion = async (
			capture: TrainingCaptureLog | null,
			notes: string | null,
			variant: string | null
		): Promise<boolean> => {
			const saved = await persistCard(card, next, date, capture, notes, variant);
			if (saved && submittingTrackedRun && selectedDate === date) {
				await reloadToday(date);
			}
			return saved;
		};
		localStatus[card.occurrence_key] = next;
		statusVersion++;
		if (expandedOccurrenceKey === card.occurrence_key) {
			cancelPendingPersist(card.occurrence_key);
			const notes = detailNote.trim() || null;
			const capture = stagedCapture;
			const variant = variantTaken;
			applyDetailSnapshot(card, capture, notes, variant);
			trackOptimisticStatus(
				card,
				next,
				previous,
				date,
				() => persistCompletion(capture, notes, variant)
			);
			return;
		}
		const capture = card.capture;
		const notes = card.notes;
		const variant = card.variant_taken;
		trackOptimisticStatus(card, next, previous, date, () =>
			persistCompletion(capture, notes, variant)
		);
	}

	function quickSkip(card: TrainingTodayCard): void {
		const date = mutationDate();
		if (date === null) return;
		const previous = effectiveStatus(card);
		localStatus[card.occurrence_key] = 'skipped';
		statusVersion++;
		const capture = card.capture;
		const notes = card.notes;
		const variant = card.variant_taken;
		trackOptimisticStatus(card, 'skipped', previous, date, () =>
			persistCard(card, 'skipped', date, capture, notes, variant)
		);
	}

	let saveTimeout: ReturnType<typeof setTimeout> | null = null;
	let pendingPersist: { key: string; run: () => void } | null = null;

	function schedulePersistDetail(card: TrainingTodayCard, delay = 500): void {
		const date = mutationDate();
		if (date === null) return;
		if (saveTimeout) clearTimeout(saveTimeout);
		const capture = stagedCapture;
		const notes = detailNote.trim() || null;
		const variant = variantTaken;
		const run = () => {
			saveTimeout = null;
			pendingPersist = null;
			applyDetailSnapshot(card, capture, notes, variant);
			// Only send `status` when the user explicitly changed it this session (an override
			// exists in `localStatus`); otherwise omit the key so the PUT can't echo the
			// *derived* status (e.g. a tracked-run auto-'completed') back into the manual log
			// and corrupt provenance — see `TrainingLogUpdateRequest` presence-vs-null semantics.
			const explicitStatus = localStatus[card.occurrence_key] as CardStatus | undefined;
			void persistCard(card, explicitStatus, date, capture, notes, variant);
		};
		pendingPersist = { key: card.occurrence_key, run };
		saveTimeout = setTimeout(run, delay);
	}

	function flushPendingPersist(): void {
		if (!saveTimeout || !pendingPersist) return;
		clearTimeout(saveTimeout);
		pendingPersist.run();
	}

	function cancelPendingPersist(key: string): void {
		if (pendingPersist?.key !== key) return;
		if (saveTimeout) clearTimeout(saveTimeout);
		saveTimeout = null;
		pendingPersist = null;
	}

	function selectVariant(card: TrainingTodayCard, option: string): void {
		variantTaken = option;
		const current = effectiveStatus(card);
		const next = statusForVariant(option, current);
		if (next !== current) {
			localStatus[card.occurrence_key] = next;
			statusVersion++;
		}
		schedulePersistDetail(card);
	}

	async function persistRunLink(
		card: TrainingTodayCard,
		patch: { linked_run_id?: string | null; run_link_detached?: boolean | null }
	): Promise<void> {
		const date = mutationDate();
		if (date === null) return;
		error = null;
		try {
			await api.updateTrainingCard(date, card.occurrence_key, patch);
			if (selectedDate === date) await reloadToday(date);
		} catch (cause: unknown) {
			if (selectedDate === date) error = errorMessage(cause);
		}
	}
</script>

<svelte:head>
	<title>Today - Garmin Stats</title>
</svelte:head>

{#if loading}
	<section class="loading-shell"><div class="loading-card">Loading today’s training…</div></section>
{:else}
	<section class="today-shell">
		<div class="header-bar">
			<div class="header-left">
				<h1>Today</h1>
				<input type="date" class="date-input" bind:value={selectedDate} />
				{#if trainingToday?.block_name}
					<span class="program-context">
						<strong>{trainingToday.block_name}</strong>
						{#if trainingToday.day !== null && trainingToday.block_days !== null}
							· Day {trainingToday.day} of {trainingToday.block_days}
						{:else if trainingToday.schedule_start}
							· Starts {fmtFullDate(parseIsoDate(trainingToday.schedule_start))}
						{/if}
					</span>
				{/if}
			</div>
			<div class="header-right">
				<div class="progress-summary">
					<span class="progress-count">{stats.completed}<span> / {stats.total}</span></span>
					<div class="progress-bar" aria-label={`${stats.completed} of ${stats.total} complete`}>
						{#if stats.total > 0}
							<div class="progress-fill completed" style={`width: ${(stats.completed / stats.total) * 100}%`}></div>
							<div class="progress-fill partial" style={`width: ${(stats.partial / stats.total) * 100}%`}></div>
							<div class="progress-fill skipped" style={`width: ${(stats.skipped / stats.total) * 100}%`}></div>
						{/if}
					</div>
				</div>
				<a class="schedule-link" href="/training/schedule">Schedule</a>
			</div>
		</div>

		{#if error}<div class="error-banner">{error}</div>{/if}

		{#if allCards.length > 0}
			<div class="filter-row" aria-label="Filter by time of day">
				{#each SLOT_ORDER as slot}
					{#if cardsForSlot(slot).length > 0}
						<button
							type="button"
							class="slot-jump"
							class:active={slotFilter === slot}
							style={`--sj-color: ${slotAccent(slot).color}`}
							onclick={() => (slotFilter = slotFilter === slot ? null : slot)}
						>
							{SLOT_LABELS[slot]}
						</button>
					{/if}
				{/each}
			</div>
		{/if}

		{#if !error && allCards.length === 0}
			<div class="empty-board">
				<span>Nothing scheduled for this date.</span>
				{#if trainingToday?.block_id}
					<a href="/training/schedule">View schedule</a>
				{:else}
					<a href="/training/import">No active block — import one</a>
				{/if}
			</div>
		{:else if !error}
			<div class="activity-list">
				{#each SLOT_ORDER as slot}
					{@const cards = cardsForSlot(slot)}
					{#if cards.length > 0 && (!slotFilter || slotFilter === slot)}
						<div class="slot-divider" style={`--sd-color: ${slotAccent(slot).color}`}>
							<span class="slot-label">{SLOT_LABELS[slot]}</span>
							<span class="slot-count">{cards.length}</span>
						</div>
						{#each cards as card (card.occurrence_key)}
							{@const theme = trainingCardTheme(card)}
							<TodayActivityRow
								status={effectiveStatus(card)}
								expanded={expandedOccurrenceKey === card.occurrence_key}
								accent={theme.accent}
								icon={theme.icon}
								name={card.card.name}
								summary={`${card.bundle_name}${card.key_session ? ' · key session' : ''}`}
								brief={trainingCardBrief(card)}
								backup={card.measurement_attempt === 'backup'}
								completionTitle={card.execution.source === 'tracked_run' && effectiveStatus(card) === 'completed'
									? 'Submit run feedback'
									: undefined}
								onToggleComplete={() => toggleComplete(card)}
								onSkip={() => quickSkip(card)}
								onToggleDetails={() => toggleDetails(card)}
							>
								<TodayCardDetails
									variantOptions={card.variant_options ?? []}
									selectedVariant={variantTaken}
									bind:note={detailNote}
									onSelectVariant={(option) => selectVariant(card, option)}
									onNoteBlur={() => schedulePersistDetail(card, 400)}
								>
									<TrainingCardBody
										{card}
										mode="log"
										onCapture={(capture) => {
											stagedCapture = capture;
											schedulePersistDetail(card);
										}}
										onRunLink={(patch) => persistRunLink(card, patch)}
									/>
								</TodayCardDetails>
							</TodayActivityRow>
						{/each}
					{/if}
				{/each}
			</div>
		{/if}
	</section>
{/if}

<style>
	.today-shell { display: flex; flex-direction: column; gap: 12px; }
	.loading-shell { padding: 32px 0; }
	.loading-card,.empty-board { border: 1px solid rgba(255,255,255,.08); border-radius: 12px; background: rgba(255,255,255,.025); color: #8fa3b0; padding: 28px; }
	.header-bar { display: flex; align-items: center; justify-content: space-between; gap: 20px; min-height: 76px; padding: 14px 20px; border: 1px solid rgba(255,255,255,.08); border-radius: 14px; background: rgba(255,255,255,.035); }
	.header-left,.header-right,.progress-summary { display: flex; align-items: center; gap: 14px; }
	h1 { margin: 0; color: #eef5f8; font-family: 'Instrument Sans',sans-serif; font-size: 28px; font-weight: 700; letter-spacing: -.02em; }
	.date-input { color-scheme: dark; border: 1px solid rgba(255,255,255,.1); background: rgba(8,15,24,.7); color: #c8d6df; border-radius: 9px; padding: 8px 10px; font-family: 'DM Mono',monospace; font-size: 13px; }
	.program-context { color: #8196a5; font-family: 'DM Mono',monospace; font-size: 11px; letter-spacing: .02em; white-space: nowrap; }
	.program-context strong { color: #b9cad4; font-weight: 500; }
	.progress-count { color: #eef5f8; font-family: 'DM Mono',monospace; font-size: 13px; }
	.progress-count span { color: #6b8292; }
	.progress-bar { display: flex; width: 120px; height: 6px; overflow: hidden; border-radius: 3px; background: rgba(255,255,255,.06); }
	.progress-fill { height: 100%; transition: width .3s ease; }
	.progress-fill.completed { background: #5bb5a6; }
	.progress-fill.partial { background: #d4944c; }
	.progress-fill.skipped { background: #e85d4a; }
	.schedule-link { border: 1px solid rgba(91,181,166,.25); border-radius: 8px; padding: 7px 12px; color: #5bb5a6; font-family: 'DM Mono',monospace; font-size: 11px; letter-spacing: .08em; text-decoration: none; text-transform: uppercase; }
	.schedule-link:hover { background: rgba(91,181,166,.1); }
	.error-banner { border: 1px solid rgba(232,93,74,.25); border-radius: 9px; background: rgba(232,93,74,.08); color: #f2a399; padding: 10px 14px; font-size: 13px; }
	.filter-row { display: flex; align-items: center; flex-wrap: wrap; gap: 6px; }
	.slot-jump { border: 1px solid color-mix(in srgb,var(--sj-color) 30%,transparent); border-radius: 7px; background: transparent; color: var(--sj-color); padding: 5px 11px; font-family: 'DM Mono',monospace; font-size: 10px; letter-spacing: .1em; text-transform: uppercase; cursor: pointer; }
	.slot-jump:hover,.slot-jump.active { background: color-mix(in srgb,var(--sj-color) 12%,transparent); }
	.slot-jump.active { border-color: color-mix(in srgb,var(--sj-color) 55%,transparent); }
	.activity-list { display: flex; flex-direction: column; gap: 6px; }
	.slot-divider { display: flex; align-items: center; gap: 10px; margin-top: 8px; padding: 10px 0 6px; border-bottom: 1px solid rgba(255,255,255,.07); }
	.slot-divider::before { width: 3px; height: 16px; border-radius: 2px; background: var(--sd-color); content: ''; }
	.slot-label { color: var(--sd-color,#8fa3b0); font-family: 'DM Mono',monospace; font-size: 11px; letter-spacing: .14em; text-transform: uppercase; }
	.slot-count { color: #6b8292; font-family: 'DM Mono',monospace; font-size: 11px; }
	.empty-board { display: flex; flex-direction: column; align-items: flex-start; gap: 8px; }
	.empty-board a { color: #5bb5a6; text-decoration: none; }
</style>
