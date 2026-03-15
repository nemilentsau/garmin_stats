<script lang="ts">
	import { onMount } from 'svelte';

	import {
		api,
		type AssistantArtifact,
		type CardTemplate,
		type RoutineAssignment,
		type RoutineSchedule
	} from '$lib/api';
	import { COLORS, withAlpha } from '$lib/colors';
	import { errorMessage } from '$lib/utils';

	let loading = $state(true);
	let error: string | null = $state(null);

	let artifacts = $state<AssistantArtifact[]>([]);
	let cards = $state<CardTemplate[]>([]);
	let routines = $state<RoutineSchedule[]>([]);
	let assignmentsByRoutine = $state<Record<string, RoutineAssignment[]>>({});

	const cardsById = $derived.by(() =>
		Object.fromEntries(cards.map((card) => [card.id, card])) as Record<string, CardTemplate>
	);
	const assignmentCount = $derived.by(() =>
		Object.values(assignmentsByRoutine).reduce((total, assignments) => total + assignments.length, 0)
	);
	const pendingArtifacts = $derived.by(() =>
		artifacts.filter((artifact) => artifact.status !== 'activated').length
	);
	const openEndedRoutines = $derived.by(() => routines.filter((routine) => routine.end_date === null).length);

	function assignmentLabel(assignment: RoutineAssignment): string {
		const card = cardsById[assignment.card_template_id];
		return card ? card.name : assignment.card_template_id;
	}

	function formatDate(date: string | null): string {
		if (!date) return 'Open-ended';
		return new Date(date).toLocaleDateString('en-US', {
			month: 'short',
			day: 'numeric',
			year: 'numeric'
		});
	}

	async function loadPage() {
		error = null;
		const [artifactsResponse, cardsResponse, routinesResponse] = await Promise.all([
			api.getAssistantArtifacts(),
			api.getCards('active'),
			api.getRoutines('active')
		]);
		artifacts = artifactsResponse.artifacts;
		cards = cardsResponse.cards;
		routines = routinesResponse.routines;

		const assignmentResponses = await Promise.all(
			routinesResponse.routines.map(async (routine) => ({
				routineId: routine.id,
				assignments: (await api.getRoutineAssignments(routine.id)).assignments
			}))
		);
		assignmentsByRoutine = Object.fromEntries(
			assignmentResponses.map((entry) => [entry.routineId, entry.assignments])
		);
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
		<div class="loading-card">Loading compiled routine schedules...</div>
	</section>
{:else}
	<section class="schedule-shell">
		<div
			class="hero"
			style={`--hero-a: ${withAlpha(COLORS.bodyBattery, '33')}; --hero-b: ${withAlpha(COLORS.respiration, '2b')};`}
		>
			<div class="hero-copy">
				<p class="eyebrow">Live Schedule</p>
				<h1>The schedule tab is the source of truth for what can appear on Today.</h1>
				<p>
					New cards and new routines should enter through creation, activate into the live runtime, then
					show up here and on Today. Today should execute this schedule, not edit around it.
				</p>
			</div>

			<div class="hero-aside">
				<div class="summary-stat">
					<span>Active routines</span>
					<strong>{routines.length}</strong>
				</div>
				<div class="summary-stat">
					<span>Recurring placements</span>
					<strong>{assignmentCount}</strong>
				</div>
				<div class="summary-stat">
					<span>Live cards</span>
					<strong>{cards.length}</strong>
				</div>
				<div class="summary-stat accent">
					<span>Drafts waiting</span>
					<strong>{pendingArtifacts}</strong>
				</div>
				<div class="action-row">
					<a class="primary-link" href="/routines/creation">Open routine creation</a>
					<a class="ghost-link" href="/today">Open today board</a>
				</div>
			</div>
		</div>

		{#if error}
			<div class="error-banner">{error}</div>
		{/if}

		<div class="summary-grid">
			<div class="summary-card">
				<span>Open-ended routines</span>
				<strong>{openEndedRoutines}</strong>
				<p>Schedules with no end date. They persist until explicitly replaced or retired.</p>
			</div>
			<div class="summary-card">
				<span>Ended by schedule</span>
				<strong>{routines.length - openEndedRoutines}</strong>
				<p>Schedules with a defined end date. Use these when a block should terminate cleanly.</p>
			</div>
			<div class="summary-card">
				<span>Cards per routine</span>
				<strong>{routines.length === 0 ? 0 : Math.round(assignmentCount / routines.length)}</strong>
				<p>A rough density check. If this climbs too high, the schedule is probably hiding too much inside one routine.</p>
			</div>
		</div>

		<div class="runtime-grid">
			<section class="panel">
				<div class="panel-head">
					<p>Compiled Schedules</p>
					<h2>Each routine is just recurrence plus assigned cards.</h2>
				</div>

				{#if routines.length === 0}
					<div class="empty-card">No live routines exist yet. Create and activate one from the creation tab.</div>
				{:else}
					<div class="runtime-list">
						{#each routines as routine}
							<article class="runtime-card">
								<div class="runtime-topline">
									<div>
										<p>{routine.cadence}</p>
										<h3>{routine.name}</h3>
									</div>
									<span>{assignmentsByRoutine[routine.id]?.length ?? 0} placements</span>
								</div>

								<div class="meta-row">
									<span>Starts {formatDate(routine.start_date)}</span>
									<span>{routine.end_date ? `Ends ${formatDate(routine.end_date)}` : 'No end date'}</span>
									<span>{routine.status}</span>
								</div>

								{#if routine.notes}
									<p class="runtime-note">{routine.notes}</p>
								{/if}

								<div class="assignment-list">
									{#each assignmentsByRoutine[routine.id] ?? [] as assignment}
										<div class="assignment-pill">
											<strong>{assignmentLabel(assignment)}</strong>
											<span>{assignment.weekday} · week {assignment.cycle_week}</span>
											<small>{assignment.slot} · position {assignment.position}</small>
										</div>
									{/each}
								</div>
							</article>
						{/each}
					</div>
				{/if}
			</section>

			<section class="panel">
				<div class="panel-head">
					<p>Live Card Library</p>
					<h2>Reusable blocks the schedule can place without more infrastructure.</h2>
				</div>

				{#if cards.length === 0}
					<div class="empty-card">No live cards exist yet. Activate a card template from the creation tab first.</div>
				{:else}
					<div class="runtime-list">
						{#each cards as card}
							<article class="runtime-card compact">
								<div class="runtime-topline">
									<div>
										<p>{card.renderer}</p>
										<h3>{card.name}</h3>
									</div>
									<span>default {card.slot_default}</span>
								</div>

								{#if card.summary}
									<p class="runtime-note">{card.summary}</p>
								{/if}

								<div class="tag-row">
									{#each card.tags as tag}
										<span>{tag}</span>
									{/each}
								</div>
							</article>
						{/each}
					</div>
				{/if}
			</section>
		</div>
	</section>
{/if}

<style>
	.schedule-shell {
		display: flex;
		flex-direction: column;
		gap: 18px;
	}

	.loading-shell {
		padding: 32px 0;
	}

	.loading-card,
	.error-banner,
	.empty-card {
		font-family: 'DM Mono', monospace;
		font-size: 12px;
		color: #95aab7;
		padding: 14px 16px;
		border-radius: 18px;
		border: 1px solid rgba(255, 255, 255, 0.08);
		background: rgba(255, 255, 255, 0.03);
	}

	.hero {
		display: grid;
		grid-template-columns: minmax(0, 1.35fr) minmax(320px, 0.95fr);
		gap: 18px;
		padding: 24px;
		border-radius: 28px;
		border: 1px solid rgba(255, 255, 255, 0.08);
		background:
			radial-gradient(circle at top left, var(--hero-a), transparent 38%),
			radial-gradient(circle at bottom right, var(--hero-b), transparent 42%),
			linear-gradient(145deg, rgba(10, 20, 32, 0.9), rgba(15, 27, 41, 0.84));
	}

	.eyebrow,
	.panel-head p,
	.runtime-topline p,
	.runtime-topline span,
	.summary-card span,
	.meta-row span,
	.assignment-pill span,
	.assignment-pill small {
		margin: 0;
		font-family: 'DM Mono', monospace;
		font-size: 11px;
		text-transform: uppercase;
		letter-spacing: 0.14em;
		color: #8fa3b0;
	}

	.hero-copy h1,
	.panel-head h2 {
		margin: 8px 0 0;
		font-size: clamp(28px, 4vw, 40px);
		line-height: 1.04;
		color: #eef5f8;
		max-width: 13ch;
	}

	.hero-copy p:last-child {
		max-width: 58ch;
		color: #abc0cb;
		line-height: 1.6;
	}

	.hero-aside,
	.summary-grid,
	.runtime-grid {
		display: grid;
		gap: 12px;
	}

	.hero-aside {
		grid-template-columns: repeat(2, minmax(0, 1fr));
		align-content: start;
	}

	.summary-stat,
	.summary-card,
	.panel,
	.runtime-card {
		padding: 16px;
		border-radius: 22px;
		background: rgba(255, 255, 255, 0.035);
		border: 1px solid rgba(255, 255, 255, 0.08);
	}

	.summary-stat span,
	.summary-card span {
		display: block;
		font-family: 'DM Mono', monospace;
		font-size: 11px;
		text-transform: uppercase;
		letter-spacing: 0.14em;
		color: #8fa3b0;
	}

	.summary-stat strong,
	.summary-card strong {
		display: block;
		margin-top: 10px;
		font-size: 30px;
	}

	.summary-stat.accent {
		background: linear-gradient(140deg, rgba(91, 181, 166, 0.12), rgba(74, 144, 217, 0.12));
	}

	.action-row,
	.runtime-grid,
	.meta-row,
	.assignment-list,
	.tag-row {
		display: flex;
		flex-wrap: wrap;
		gap: 10px;
	}

	.action-row {
		grid-column: 1 / -1;
		margin-top: 4px;
	}

	.primary-link,
	.ghost-link {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		padding: 11px 14px;
		border-radius: 999px;
		text-decoration: none;
		font-weight: 700;
	}

	.primary-link {
		background: linear-gradient(135deg, rgba(91, 181, 166, 0.92), rgba(74, 144, 217, 0.88));
		color: #08111d;
	}

	.ghost-link {
		background: rgba(255, 255, 255, 0.05);
		color: #d3dfe7;
	}

	.summary-grid {
		grid-template-columns: repeat(3, minmax(0, 1fr));
	}

	.summary-card p,
	.runtime-note {
		margin: 10px 0 0;
		color: #a8bac6;
		line-height: 1.55;
	}

	.runtime-grid {
		display: grid;
		grid-template-columns: minmax(0, 1.2fr) minmax(0, 0.8fr);
	}

	.panel {
		display: flex;
		flex-direction: column;
		gap: 14px;
	}

	.panel-head h2 {
		font-size: 24px;
		max-width: none;
	}

	.runtime-list {
		display: flex;
		flex-direction: column;
		gap: 12px;
	}

	.runtime-topline {
		display: flex;
		align-items: flex-start;
		justify-content: space-between;
		gap: 12px;
	}

	.runtime-topline h3 {
		margin: 8px 0 0;
		font-size: 22px;
	}

	.meta-row {
		margin-top: 10px;
	}

	.assignment-pill,
	.tag-row span {
		padding: 10px 12px;
		border-radius: 16px;
		background: rgba(255, 255, 255, 0.04);
	}

	.assignment-pill strong,
	.tag-row span {
		display: block;
		color: #d6e4ec;
	}

	@media (max-width: 980px) {
		.hero,
		.summary-grid,
		.runtime-grid {
			grid-template-columns: 1fr;
		}

		.hero-aside {
			grid-template-columns: repeat(2, minmax(0, 1fr));
		}
	}

	@media (max-width: 640px) {
		.hero-aside {
			grid-template-columns: 1fr;
		}
	}
</style>
