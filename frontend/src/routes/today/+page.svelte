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
		exercises?: { id: string; label: string; detail?: string; reps?: string; duration_seconds?: number }[];
	};

	const slotAccent: Record<string, SlotAccent> = {
		morning: { color: COLORS.respiration, shadow: withAlpha(COLORS.respiration, '30') },
		midday: { color: COLORS.spo2, shadow: withAlpha(COLORS.spo2, '30') },
		evening: { color: COLORS.hrv, shadow: withAlpha(COLORS.hrv, '30') },
		anytime: { color: COLORS.stress, shadow: withAlpha(COLORS.stress, '30') }
	};

	let loading = $state(true);
	let saving = $state(false);
	let error: string | null = $state(null);
	let selectedDate = $state(localDateIso());
	let today = $state<TodayResponse | null>(null);

	let expandedOccurrenceKey = $state<string | null>(null);
	let detailStatus = $state<'completed' | 'partial' | 'skipped'>('completed');
	let detailDuration = $state<number | null>(null);
	let detailNote = $state('');
	let detailRatings = $state<Record<string, number | null>>({});
	let detailItemStates = $state<Record<string, boolean>>({});

	let todayRequestToken = 0;

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
		void loadToday(date, requestToken).catch((e: unknown) => {
			error = errorMessage(e);
		});
	});

	function slotCount(slot: string): number {
		return today?.slots.find((item) => item.slot === slot)?.cards.length ?? 0;
	}

	function scrollToSlot(slot: string) {
		const section = document.getElementById(`slot-${slot}`);
		if (!section) return;
		section.scrollIntoView({ behavior: 'smooth', block: 'start' });
	}

	function initializeDetailState(card: NonNullable<TodayResponse>['slots'][number]['cards'][number]) {
		const actual = isRecord(card.actual_json) ? card.actual_json : {};
		detailStatus = card.status === 'pending' ? 'completed' : card.status;
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

	function toggleDetails(card: NonNullable<TodayResponse>['slots'][number]['cards'][number]) {
		if (expandedOccurrenceKey === card.occurrence_key) {
			expandedOccurrenceKey = null;
			return;
		}
		expandedOccurrenceKey = card.occurrence_key;
		initializeDetailState(card);
	}

	async function quickLog(
		card: NonNullable<TodayResponse>['slots'][number]['cards'][number],
		status: 'completed' | 'skipped' = 'completed'
	) {
		saving = true;
		error = null;
		try {
			await api.updateTodayCard(selectedDate, card.occurrence_key, {
				card_template_id: card.card_template_id,
				assignment_id: card.assignment_id,
				status,
				actual_json: isRecord(card.actual_json) ? card.actual_json : {},
				notes: card.notes ?? null
			});
			today = await api.getToday(selectedDate);
		} catch (e: unknown) {
			error = errorMessage(e);
		} finally {
			saving = false;
		}
	}

	async function saveDetails(card: NonNullable<TodayResponse>['slots'][number]['cards'][number]) {
		saving = true;
		error = null;
		try {
			const actual_json: Record<string, unknown> = {};
			if (card.renderer === 'timer_session') {
				if (detailDuration !== null) actual_json.actual_minutes = detailDuration;
				actual_json.ratings = detailRatings;
			} else {
				actual_json.item_states = detailItemStates;
			}

			await api.updateTodayCard(selectedDate, card.occurrence_key, {
				card_template_id: card.card_template_id,
				assignment_id: card.assignment_id,
				status: detailStatus,
				actual_json,
				notes: detailNote.trim() || null
			});
			expandedOccurrenceKey = null;
			today = await api.getToday(selectedDate);
		} catch (e: unknown) {
			error = errorMessage(e);
		} finally {
			saving = false;
		}
	}

	function formatSeconds(totalSeconds: number): string {
		if (totalSeconds < 60) return `${totalSeconds}s`;
		const minutes = Math.floor(totalSeconds / 60);
		const seconds = totalSeconds % 60;
		return seconds === 0 ? `${minutes}m` : `${minutes}m ${seconds}s`;
	}

	function cardContextLabel(card: NonNullable<TodayResponse>['slots'][number]['cards'][number]): string | null {
		if (card.routine_name) return card.routine_name;
		if (card.schedule_override_action) return 'Schedule override';
		return null;
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
		<div class="hero">
			<div class="hero-copy">
				<p class="eyebrow">Live Routine Board</p>
				<h1>Today is compiled from activated specs, not templates glued into code.</h1>
				<p class="hero-text">
					Each card below comes from the live schedule. Tap once to log it, or open the card when you
					need detail. Today records what happened; it does not rewrite the schedule. If the plan is
					wrong, fix it in routines creation instead.
				</p>
			</div>

			<div class="hero-tools">
				<label class="date-control">
					<span>Date</span>
					<input type="date" bind:value={selectedDate} />
				</label>
				<a class="hero-link" href="/routines/creation">Change routines here</a>
			</div>
		</div>

		<div class="summary-row">
			<div class="summary-stat">
				<span>Total cards</span>
				<strong>{today?.stats.total ?? 0}</strong>
			</div>
			<div class="summary-stat">
				<span>Completed</span>
				<strong>{today?.stats.completed ?? 0}</strong>
			</div>
			<div class="summary-stat">
				<span>Pending</span>
				<strong>{today?.stats.pending ?? 0}</strong>
			</div>
			<div class="summary-stat accent">
				<span>Partial / skipped</span>
				<strong>{(today?.stats.partial ?? 0) + (today?.stats.skipped ?? 0)}</strong>
			</div>
		</div>

		{#if error}
			<div class="error-banner">{error}</div>
		{/if}

		<div class="bookmark-strip">
			{#each today?.slots ?? [] as slot}
				<button
					class="bookmark"
					style={`--bookmark-color: ${slotAccent[slot.slot]?.color ?? '#8a9baa'}; --bookmark-shadow: ${slotAccent[slot.slot]?.shadow ?? 'transparent'};`}
					onclick={() => scrollToSlot(slot.slot)}
				>
					<span>{slot.label}</span>
					<strong>{slotCount(slot.slot)}</strong>
				</button>
			{/each}
		</div>

		<div class="slot-stack">
			{#each today?.slots ?? [] as slot}
				<section
					class="slot-section"
					id={`slot-${slot.slot}`}
					style={`--slot-accent: ${slotAccent[slot.slot]?.color ?? '#8a9baa'}; --slot-glow: ${slotAccent[slot.slot]?.shadow ?? 'transparent'};`}
				>
					<div class="slot-head">
						<div>
							<p>{slot.label}</p>
							<h2>{slot.cards.length === 0 ? 'Nothing scheduled here.' : `${slot.cards.length} live cards`}</h2>
						</div>
						<span>{slot.slot}</span>
					</div>

					{#if slot.cards.length === 0}
						<div class="slot-empty">This slot is open. If it should be filled, change the routine schedule instead of patching Today.</div>
					{:else}
						<div class="card-column">
							{#each slot.cards as card}
								<div class="today-card" class:expanded={expandedOccurrenceKey === card.occurrence_key}>
									<div class="card-topline">
										<div class="card-meta">
											<div class="status-dot" class:done={card.status === 'completed'} class:partial={card.status === 'partial'} class:skipped={card.status === 'skipped'}></div>
											<span>{card.renderer.replace('_', ' ')}</span>
											{#if cardContextLabel(card)}
												<small>{cardContextLabel(card)}</small>
											{/if}
										</div>
										<span class="status-pill" class:done={card.status === 'completed'} class:partial={card.status === 'partial'} class:skipped={card.status === 'skipped'}>
											{card.status}
										</span>
									</div>

									<div class="card-body">
										<div class="card-copy">
											<h3>{card.name}</h3>
											{#if card.summary}
												<p>{card.summary}</p>
											{/if}
											<div class="tag-row">
												{#each card.tags as tag}
													<span>{tag}</span>
												{/each}
											</div>
										</div>

										<div class="card-actions">
											<button class="done-btn" onclick={() => quickLog(card, 'completed')} disabled={saving}>
												Done
											</button>
											<button class="ghost-btn" onclick={() => quickLog(card, 'skipped')} disabled={saving}>
												Skip
											</button>
											<button class="ghost-btn" onclick={() => toggleDetails(card)}>
												{expandedOccurrenceKey === card.occurrence_key ? 'Close' : 'Details'}
											</button>
										</div>
									</div>

									{#if card.renderer === 'timer_session'}
										{@const payload = timerPayload(card.payload_json as Record<string, unknown>)}
										<div class="payload-strip">
											{#if payload.duration_minutes}
												<span>{payload.duration_minutes} min prescribed</span>
											{/if}
											{#if payload.pattern}
												<span>{payload.pattern}</span>
											{/if}
										</div>
									{:else if card.renderer === 'checklist_block'}
										{@const payload = checklistPayload(card.payload_json as Record<string, unknown>)}
										<div class="payload-strip">
											<span>{payload.items?.length ?? 0} checklist items</span>
										</div>
									{:else}
										{@const payload = exercisePayload(card.payload_json as Record<string, unknown>)}
										<div class="payload-strip">
											<span>{payload.exercises?.length ?? 0} exercises</span>
										</div>
									{/if}

									{#if expandedOccurrenceKey === card.occurrence_key}
										<div class="detail-panel">
											{#if card.renderer === 'timer_session'}
												{@const payload = timerPayload(card.payload_json as Record<string, unknown>)}
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
													<input type="number" bind:value={detailDuration} min="0" />
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
																/>
															</label>
														{/each}
													</div>
												{/if}
											{:else if card.renderer === 'checklist_block'}
												{@const payload = checklistPayload(card.payload_json as Record<string, unknown>)}
												{#if payload.instructions}
													<p class="detail-copy">{payload.instructions}</p>
												{/if}
												<div class="checklist">
													{#each payload.items ?? [] as item}
														<label class="check-item">
															<input type="checkbox" bind:checked={detailItemStates[item.id]} />
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
												{@const payload = exercisePayload(card.payload_json as Record<string, unknown>)}
												{#if payload.instructions}
													<p class="detail-copy">{payload.instructions}</p>
												{/if}
												<div class="checklist">
													{#each payload.exercises ?? [] as exercise}
														<label class="check-item">
															<input type="checkbox" bind:checked={detailItemStates[exercise.id]} />
															<div>
																<strong>{exercise.label}</strong>
																<small>
																	{exercise.detail ?? exercise.reps ?? ''}
																	{#if exercise.duration_seconds}
																		{exercise.detail || exercise.reps ? ' · ' : ''}{formatSeconds(exercise.duration_seconds)}
																	{/if}
																</small>
															</div>
														</label>
													{/each}
												</div>
											{/if}

											<div class="detail-footer">
												<label class="detail-field">
													<span>Completion</span>
													<select bind:value={detailStatus}>
														<option value="completed">completed</option>
														<option value="partial">partial</option>
														<option value="skipped">skipped</option>
													</select>
												</label>
												<label class="detail-field wide">
													<span>Notes</span>
													<textarea
														bind:value={detailNote}
														rows="3"
														placeholder="Only record what matters."
													></textarea>
												</label>
											</div>
											<button class="primary-action" onclick={() => saveDetails(card)} disabled={saving}>
												Save detail
											</button>
										</div>
									{/if}
								</div>
							{/each}
						</div>
					{/if}
				</section>
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
		gap: 18px;
	}

	.loading-shell {
		padding: 32px 0;
	}

	.loading-card,
	.error-banner,
	.slot-empty {
		font-family: 'DM Mono', monospace;
		font-size: 12px;
		color: #8fa3b0;
		border: 1px solid rgba(255, 255, 255, 0.08);
		background: rgba(255, 255, 255, 0.02);
		border-radius: 18px;
		padding: 14px 16px;
	}

	.hero {
		display: grid;
		grid-template-columns: minmax(0, 1.7fr) minmax(300px, 0.9fr);
		gap: 18px;
		padding: 22px 24px;
		border-radius: 28px;
		background:
			radial-gradient(circle at top left, rgba(91, 181, 166, 0.18), transparent 42%),
			radial-gradient(circle at bottom right, rgba(155, 107, 205, 0.18), transparent 38%),
			linear-gradient(145deg, rgba(8, 17, 29, 0.92), rgba(15, 28, 42, 0.82));
		border: 1px solid rgba(255, 255, 255, 0.08);
		box-shadow: 0 24px 70px rgba(0, 0, 0, 0.2);
	}

	.eyebrow,
	.slot-head p,
	.date-control span,
	.detail-field span {
		margin: 0;
		font-family: 'DM Mono', monospace;
		font-size: 11px;
		letter-spacing: 0.16em;
		text-transform: uppercase;
		color: #8fa3b0;
	}

	.hero-copy h1,
	.slot-head h2 {
		margin: 8px 0 0;
		font-family: 'Instrument Sans', sans-serif;
		font-size: clamp(28px, 4vw, 40px);
		line-height: 1.04;
		color: #eef5f8;
		max-width: 12ch;
	}

	.hero-text {
		max-width: 60ch;
		margin: 16px 0 0;
		color: #a7bac6;
		line-height: 1.6;
	}

	.hero-tools {
		display: flex;
		flex-direction: column;
		gap: 12px;
		padding: 16px;
		border-radius: 22px;
		background: rgba(255, 255, 255, 0.045);
		border: 1px solid rgba(255, 255, 255, 0.08);
	}

	.date-control,
	.detail-field {
		display: flex;
		flex-direction: column;
		gap: 8px;
	}

	input,
	select,
	textarea {
		border: 1px solid rgba(255, 255, 255, 0.1);
		background: rgba(8, 15, 24, 0.85);
		color: #eef5f8;
		border-radius: 14px;
		padding: 11px 12px;
		font: inherit;
	}

	textarea {
		resize: vertical;
	}

	.hero-link,
	.primary-action,
	.done-btn,
	.ghost-btn,
	.bookmark {
		border: 0;
		cursor: pointer;
		font: inherit;
	}

	.hero-link,
	.primary-action,
	.done-btn {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		padding: 12px 14px;
		border-radius: 999px;
		background: linear-gradient(135deg, rgba(91, 181, 166, 0.92), rgba(74, 144, 217, 0.88));
		color: #08111d;
		font-weight: 700;
		text-decoration: none;
	}

	.summary-row {
		display: grid;
		grid-template-columns: repeat(4, minmax(0, 1fr));
		gap: 12px;
	}

	.summary-stat {
		padding: 16px 18px;
		border-radius: 22px;
		background: rgba(255, 255, 255, 0.035);
		border: 1px solid rgba(255, 255, 255, 0.08);
	}

	.summary-stat span {
		display: block;
		font-family: 'DM Mono', monospace;
		font-size: 11px;
		color: var(--muted);
		text-transform: uppercase;
		letter-spacing: 0.14em;
	}

	.summary-stat strong {
		display: block;
		margin-top: 10px;
		font-size: 30px;
		font-family: 'Instrument Sans', sans-serif;
	}

	.summary-stat.accent {
		background: linear-gradient(140deg, rgba(91, 181, 166, 0.12), rgba(155, 107, 205, 0.12));
	}

	.detail-copy {
		margin: 0;
		color: #a7bac6;
		line-height: 1.55;
	}

	.bookmark-strip {
		display: flex;
		flex-wrap: wrap;
		gap: 10px;
	}

	.bookmark {
		display: inline-flex;
		align-items: center;
		gap: 12px;
		padding: 12px 16px;
		border-radius: 18px 18px 10px 10px;
		background: linear-gradient(180deg, var(--bookmark-shadow), rgba(255, 255, 255, 0.02));
		border: 1px solid color-mix(in srgb, var(--bookmark-color) 35%, rgba(255, 255, 255, 0.08));
		color: #dce7ee;
		box-shadow: inset 0 -1px 0 rgba(255, 255, 255, 0.05);
	}

	.bookmark span {
		font-family: 'DM Mono', monospace;
		font-size: 11px;
		letter-spacing: 0.12em;
		text-transform: uppercase;
	}

	.bookmark strong {
		font-size: 18px;
	}

	.slot-stack {
		display: flex;
		flex-direction: column;
		gap: 18px;
	}

	.slot-section {
		padding: 18px;
		border-radius: 26px;
		background:
			radial-gradient(circle at top right, var(--slot-glow), transparent 36%),
			rgba(255, 255, 255, 0.03);
		border: 1px solid rgba(255, 255, 255, 0.08);
		box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.04);
	}

	.slot-head {
		display: flex;
		align-items: flex-end;
		justify-content: space-between;
		gap: 16px;
		margin-bottom: 16px;
	}

	.slot-head h2 {
		font-size: 24px;
		max-width: none;
	}

	.slot-head > span {
		color: var(--slot-accent);
		font-family: 'DM Mono', monospace;
		text-transform: uppercase;
		letter-spacing: 0.14em;
		font-size: 11px;
	}

	.card-column {
		display: flex;
		flex-direction: column;
		gap: 12px;
	}

	.today-card {
		padding: 16px;
		border-radius: 22px;
		background: var(--paper);
		border: 1px solid var(--paper-border);
		backdrop-filter: blur(8px);
	}

	.card-topline,
	.card-body,
	.card-actions,
	.card-meta,
	.payload-strip,
	.detail-row,
	.detail-footer {
		display: flex;
		align-items: center;
		gap: 10px;
	}

	.card-topline,
	.card-body {
		justify-content: space-between;
	}

	.card-meta span,
	.card-meta small,
	.payload-strip span,
	.status-pill {
		font-family: 'DM Mono', monospace;
		font-size: 11px;
		color: #8fa3b0;
		letter-spacing: 0.1em;
		text-transform: uppercase;
	}

	.status-dot {
		width: 10px;
		height: 10px;
		border-radius: 999px;
		background: rgba(255, 255, 255, 0.16);
	}

	.status-dot.done,
	.status-pill.done {
		background: rgba(91, 181, 166, 0.18);
		color: #7be0d0;
	}

	.status-dot.partial,
	.status-pill.partial {
		background: rgba(212, 148, 76, 0.18);
		color: #f3bf81;
	}

	.status-dot.skipped,
	.status-pill.skipped {
		background: rgba(232, 93, 74, 0.18);
		color: #f2a399;
	}

	.status-dot.done,
	.status-dot.partial,
	.status-dot.skipped {
		width: 10px;
		height: 10px;
	}

	.status-pill {
		padding: 7px 10px;
		border-radius: 999px;
		background: rgba(255, 255, 255, 0.05);
	}

	.card-copy h3 {
		margin: 10px 0 4px;
		font-size: 22px;
	}

	.card-copy p {
		margin: 0;
		color: #9fb3c1;
		line-height: 1.5;
	}

	.tag-row {
		display: flex;
		flex-wrap: wrap;
		gap: 8px;
		margin-top: 12px;
	}

	.tag-row span {
		padding: 6px 10px;
		border-radius: 999px;
		background: rgba(255, 255, 255, 0.05);
		font-family: 'DM Mono', monospace;
		font-size: 11px;
		color: #c3d3dd;
	}

	.card-actions {
		flex-wrap: wrap;
		justify-content: flex-end;
		min-width: 240px;
	}

	.ghost-btn {
		padding: 11px 13px;
		border-radius: 999px;
		background: rgba(255, 255, 255, 0.05);
		color: #d5e2ea;
	}

	.payload-strip {
		flex-wrap: wrap;
		margin-top: 14px;
		padding-top: 14px;
		border-top: 1px dashed rgba(255, 255, 255, 0.08);
	}

	.detail-panel {
		margin-top: 16px;
		padding-top: 16px;
		border-top: 1px solid rgba(255, 255, 255, 0.08);
		display: flex;
		flex-direction: column;
		gap: 14px;
	}

	.detail-list,
	.checklist {
		display: grid;
		gap: 8px;
	}

	.detail-row {
		justify-content: space-between;
		padding: 10px 12px;
		border-radius: 14px;
		background: rgba(255, 255, 255, 0.03);
	}

	.ratings-grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
		gap: 10px;
	}

	.check-item {
		display: grid;
		grid-template-columns: auto minmax(0, 1fr);
		gap: 12px;
		padding: 12px 14px;
		border-radius: 16px;
		background: rgba(255, 255, 255, 0.03);
	}

	.check-item small {
		display: block;
		margin-top: 4px;
		color: #90a7b5;
	}

	.detail-footer {
		align-items: stretch;
	}

	.detail-field.wide {
		flex: 1;
	}

	@media (max-width: 900px) {
		.hero,
		.summary-row {
			grid-template-columns: 1fr;
		}

		.card-body,
		.detail-footer {
			flex-direction: column;
			align-items: flex-start;
		}

		.card-actions {
			justify-content: flex-start;
			min-width: 0;
		}
	}
</style>
