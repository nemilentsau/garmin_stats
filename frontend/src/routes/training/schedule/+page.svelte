<script lang="ts">
	import { onMount } from 'svelte';

	import { api, type TrainingScheduleWindow } from '$lib/api';
	import { addDays, isIsoDateString, localDateIso, parseIsoDate } from '$lib/date';
	import { createLatestLoader } from '$lib/realtime-page';
	import TrainingCardBody from '$lib/training/TrainingCardBody.svelte';
	import {
		SLOT_LABELS,
		SLOT_ORDER,
		slotAccent,
		trainingCardBrief,
		trainingCardTheme
	} from '$lib/training/training-display';
	import { errorMessage } from '$lib/utils';

	let loading = $state(true);
	let error: string | null = $state(null);
	let windowStartDate = $state(localDateIso());
	let loadedStartDate = $state<string | null>(null);
	let schedule = $state<TrainingScheduleWindow | null>(null);
	let expandedOccurrenceKey = $state<string | null>(null);

	const scheduledDays = $derived(schedule?.days.filter((day) => day.cards.length > 0) ?? []);
	const shortDateFormat = new Intl.DateTimeFormat('en-US', { month: 'short', day: 'numeric' });
	const weekdayFormat = new Intl.DateTimeFormat('en-US', { weekday: 'long' });
	const REQUIRED_ACTION_LABELS = { extend_block: 'Extend block', flag: 'Flag' } as const;

	function formatShortDate(date: string): string {
		return shortDateFormat.format(parseIsoDate(date));
	}

	function formatWeekday(date: string): string {
		return weekdayFormat.format(parseIsoDate(date));
	}

	function readInitialStart(): string {
		const requested = new URL(window.location.href).searchParams.get('start_date');
		return requested && isIsoDateString(requested) ? requested : localDateIso();
	}

	const loadSchedule = createLatestLoader({
		onStart: (start: string) => {
			windowStartDate = start;
			loadedStartDate = null;
			schedule = null;
			loading = true;
			error = null;
		},
		load: (start: string) => api.getTrainingScheduleWindow(start, 14),
		onSuccess: (response) => {
			schedule = response as TrainingScheduleWindow;
			windowStartDate = response.start_date;
			loadedStartDate = response.start_date;
		},
		onError: (cause) => {
			error = errorMessage(cause);
		},
		onSettled: () => {
			loading = false;
		}
	});

	async function moveWindow(days: number): Promise<void> {
		expandedOccurrenceKey = null;
		await loadSchedule(addDays(loadedStartDate ?? windowStartDate, days));
	}

	async function submitWindowStart(): Promise<void> {
		expandedOccurrenceKey = null;
		await loadSchedule(windowStartDate);
	}

	onMount(() => {
		windowStartDate = readInitialStart();
		void loadSchedule(windowStartDate);
	});
</script>

<svelte:head>
	<title>Schedule - Garmin Stats</title>
</svelte:head>

{#if loading}
	<section class="loading-shell"><div class="loading-card">Loading the next 14 days…</div></section>
{:else}
	<section class="schedule-shell">
		<div class="header-bar">
			<div class="header-left">
				<h1>Schedule</h1>
				{#if schedule}
					<span class="window-range">{formatShortDate(schedule.start_date)} – {formatShortDate(schedule.end_date)}</span>
				{/if}
			</div>
			<div class="header-right">
				<button type="button" class="nav-btn" onclick={() => void moveWindow(-7)} title="Back 7 days" aria-label="Back 7 days">
					<svg viewBox="0 0 16 16" width="14" height="14" fill="none"><path d="M10 3L5 8L10 13" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>
				</button>
				<input type="date" class="date-input" bind:value={windowStartDate} onchange={() => void submitWindowStart()} />
				<button type="button" class="nav-btn" onclick={() => void moveWindow(7)} title="Forward 7 days" aria-label="Forward 7 days">
					<svg viewBox="0 0 16 16" width="14" height="14" fill="none"><path d="M6 3L11 8L6 13" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>
				</button>
				<a class="import-link" href="/training/import">Import</a>
			</div>
		</div>

		{#if error}<div class="error-banner">{error}</div>{/if}

		{#if schedule && schedule.required_actions.length > 0}
			<div class="required-actions-row">
				<span class="required-actions-label">Program action</span>
				<ul class="required-actions" aria-label="Required program actions">
					{#each schedule.required_actions as action (action.event_id)}
						<li><strong>{REQUIRED_ACTION_LABELS[action.action]}</strong><span>{action.event_id}</span></li>
					{/each}
				</ul>
			</div>
		{/if}

		{#if !error && scheduledDays.length === 0}
			<div class="empty-state">
				<span>No training is scheduled in this window.</span>
				<a href="/training/import">Import an active block</a>
			</div>
		{:else if !error}
			<div class="timeline">
				{#each scheduledDays as day (day.date)}
					<div class="day-row">
						<div class="date-column">
							<span class="weekday">{formatWeekday(day.date)}</span>
							<span class="date-label">{formatShortDate(day.date)}</span>
							<span class="day-index">Day {day.day}</span>
						</div>
						<div class="day-content">
							{#each SLOT_ORDER as slot}
								{@const cards = day.cards.filter((card) => card.slot === slot)}
								{#if cards.length > 0}
									<div class="slot-heading" style={`--slot-color: ${slotAccent(slot).color}`}>
										<span>{SLOT_LABELS[slot]}</span><span>{cards.length}</span>
									</div>
									{#each cards as card (card.occurrence_key)}
										{@const theme = trainingCardTheme(card)}
										{@const expanded = expandedOccurrenceKey === card.occurrence_key}
										<div
											class="timeline-card"
											class:expanded
											class:done={card.status === 'completed'}
											class:skipped={card.status === 'skipped'}
											style={`--card-color: ${theme.accent}`}
										>
											<button type="button" class="card-main" onclick={() => (expandedOccurrenceKey = expanded ? null : card.occurrence_key)}>
												<span class="status-mark" class:complete={card.status === 'completed'} class:partial={card.status === 'partial'} class:skip={card.status === 'skipped'}></span>
												{#if theme.icon}<span class="domain-icon">{theme.icon}</span>{/if}
												<div class="card-content">
													<span class="card-name">{card.card.name}</span>
													<span class="card-summary">{card.bundle_name}{#if card.key_session} · key session{/if}{#if card.measurement_attempt === 'backup'} · Backup test{/if}</span>
												</div>
												<span class="card-brief">{trainingCardBrief(card)}</span>
												<svg class="chevron" class:rotated={expanded} viewBox="0 0 16 16" width="14" height="14" fill="none"><path d="M4 6L8 10L12 6" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>
											</button>
											{#if expanded}<div class="detail-panel"><TrainingCardBody {card} mode="view" /></div>{/if}
										</div>
									{/each}
								{/if}
							{/each}
						</div>
					</div>
				{/each}
			</div>
		{/if}
	</section>
{/if}

<style>
	.schedule-shell { display: flex; flex-direction: column; gap: 12px; }
	.loading-shell { padding: 32px 0; }
	.loading-card,.empty-state { border: 1px solid rgba(255,255,255,.08); border-radius: 12px; background: rgba(255,255,255,.025); color: #8fa3b0; padding: 28px; }
	.header-bar { display: flex; align-items: center; justify-content: space-between; gap: 20px; min-height: 76px; padding: 14px 20px; border: 1px solid rgba(255,255,255,.08); border-radius: 14px; background: rgba(255,255,255,.035); }
	.header-left,.header-right { display: flex; align-items: center; gap: 12px; }
	h1 { margin: 0; color: #eef5f8; font-family: 'Instrument Sans',sans-serif; font-size: 28px; font-weight: 700; letter-spacing: -.02em; }
	.window-range,.day-index { color: #6f8798; font-family: 'DM Mono',monospace; font-size: 11px; }
	.nav-btn { display: grid; width: 32px; height: 32px; place-items: center; border: 1px solid rgba(255,255,255,.08); border-radius: 8px; background: transparent; color: #8fa3b0; cursor: pointer; }
	.nav-btn:hover { background: rgba(255,255,255,.05); color: #c8d6df; }
	.date-input { color-scheme: dark; border: 1px solid rgba(255,255,255,.1); background: rgba(8,15,24,.7); color: #c8d6df; border-radius: 8px; padding: 7px 9px; font-family: 'DM Mono',monospace; font-size: 12px; }
	.import-link { border: 1px solid rgba(91,181,166,.28); border-radius: 8px; color: #5bb5a6; padding: 7px 11px; font-family: 'DM Mono',monospace; font-size: 10px; letter-spacing: .08em; text-decoration: none; text-transform: uppercase; }
	.error-banner { border: 1px solid rgba(232,93,74,.25); border-radius: 9px; background: rgba(232,93,74,.08); color: #f2a399; padding: 10px 14px; font-size: 13px; }
	.required-actions-row { display: flex; align-items: flex-start; gap: 16px; border: 1px solid rgba(212,148,76,.2); border-radius: 10px; background: rgba(212,148,76,.06); padding: 12px 14px; }
	.required-actions-label,.slot-heading { font-family: 'DM Mono',monospace; font-size: 10px; letter-spacing: .12em; text-transform: uppercase; }
	.required-actions-label { color: #d4944c; }
	.required-actions { display: flex; flex-wrap: wrap; gap: 12px; margin: 0; padding: 0; list-style: none; }
	.required-actions li { display: flex; gap: 6px; color: #8fa3b0; font-size: 12px; }
	.required-actions strong { color: #d9b17d; }
	.timeline { display: flex; flex-direction: column; }
	.day-row { display: grid; grid-template-columns: 120px minmax(0,1fr); gap: 18px; padding: 16px 0 20px; border-bottom: 1px solid rgba(255,255,255,.07); }
	.date-column { display: flex; flex-direction: column; gap: 3px; padding-top: 4px; }
	.weekday { color: #c8d6df; font-size: 13px; font-weight: 600; }
	.date-label { color: #8fa3b0; font-family: 'DM Mono',monospace; font-size: 12px; }
	.day-content { display: flex; min-width: 0; flex-direction: column; gap: 6px; }
	.slot-heading { display: flex; align-items: center; gap: 8px; margin-top: 8px; color: var(--slot-color); }
	.slot-heading::before { width: 3px; height: 13px; border-radius: 2px; background: var(--slot-color); content: ''; }
	.slot-heading span:last-child { color: #5e7282; }
	.timeline-card { border: 1px solid rgba(255,255,255,.055); border-left: 3px solid var(--card-color); border-radius: 9px; background: rgba(255,255,255,.025); }
	.timeline-card.done,.timeline-card.skipped { opacity: .5; }
	.timeline-card.expanded { opacity: 1; border-color: rgba(255,255,255,.1); background: rgba(255,255,255,.04); }
	.card-main { display: flex; width: 100%; min-height: 50px; align-items: center; gap: 10px; border: 0; background: transparent; color: inherit; padding: 10px 13px; text-align: left; cursor: pointer; }
	.status-mark { width: 9px; height: 9px; flex: 0 0 auto; border: 1px solid #5e7282; border-radius: 50%; }
	.status-mark.complete { border-color: #5bb5a6; background: #5bb5a6; }
	.status-mark.partial { border-color: #d4944c; background: #d4944c; }
	.status-mark.skip { border-color: #e85d4a; background: #e85d4a; }
	.domain-icon { font-size: 14px; opacity: .8; }
	.card-content { display: flex; min-width: 0; flex: 1; flex-direction: column; }
	.card-name { overflow: hidden; color: #eef5f8; font-size: 14px; font-weight: 600; text-overflow: ellipsis; white-space: nowrap; }
	.card-summary { overflow: hidden; color: #7f95a6; font-size: 12px; text-overflow: ellipsis; white-space: nowrap; }
	.card-brief { flex: 0 0 auto; color: #6b8292; font-family: 'DM Mono',monospace; font-size: 11px; }
	.chevron { flex: 0 0 auto; color: #6b8292; transition: transform .2s; }
	.chevron.rotated { transform: rotate(180deg); }
	.detail-panel { border-top: 1px solid rgba(255,255,255,.06); padding: 14px; }
	.empty-state { display: flex; flex-direction: column; align-items: flex-start; gap: 8px; }
	.empty-state a { color: #5bb5a6; text-decoration: none; }
</style>
