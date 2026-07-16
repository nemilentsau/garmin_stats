<svelte:head>
	<title>Runs - Garmin Stats</title>
</svelte:head>

<script lang="ts">
	import { onMount } from 'svelte';
	import { api, type RunListItem } from '$lib/api';
	import { startRealtimePage } from '$lib/realtime-page';
	import { errorMessage } from '$lib/utils';
	import { parseIsoDate, fmtWeekdayDayMonth } from '$lib/date';
	import {
		fmtMiBare,
		fmtDuration,
		fmtPaceBare,
		fmtStartTime,
		fmtLoad,
		fmtTE,
		hrBadgeLabel
	} from '$lib/format-run';

	let runs: RunListItem[] = $state([]);
	let loading = $state(true);
	let error: string | null = $state(null);
	let fromDate = $state('');
	let toDate = $state('');

	async function loadRuns() {
		const res = await api.getRuns(fromDate || undefined, toDate || undefined);
		runs = res.runs;
	}

	function setError(e: string | null) {
		error = e;
	}
	function setLoading(v: boolean) {
		loading = v;
	}

	onMount(() => startRealtimePage({ fetchData: loadRuns, setError, setLoading }));

	function applyFilter(): void {
		loading = true;
		loadRuns()
			.then(() => {
				error = null;
			})
			.catch((e: unknown) => {
				error = errorMessage(e);
			})
			.finally(() => {
				loading = false;
			});
	}

	function clearFilter(): void {
		fromDate = '';
		toDate = '';
		applyFilter();
	}

	/* Formatting is imported from $lib/format-run (shared with /runs/[id]) — the backend
	   supplies every value below, including the already-derived pace field. Nothing here
	   computes or aggregates. */
</script>

<div class="runs-page">
	<div class="page-header">
		<h1>Runs</h1>
		<div class="filters">
			<label class="filter-field">
				<span>From</span>
				<input
					type="date"
					class="date-input"
					bind:value={fromDate}
					max={toDate || undefined}
					onchange={applyFilter}
				/>
			</label>
			<label class="filter-field">
				<span>To</span>
				<input
					type="date"
					class="date-input"
					bind:value={toDate}
					min={fromDate || undefined}
					onchange={applyFilter}
				/>
			</label>
			{#if fromDate || toDate}
				<button type="button" class="clear-btn" onclick={clearFilter}>Clear</button>
			{/if}
		</div>
	</div>

	{#if error}
		<div class="error-banner">{error}</div>
	{/if}

	{#if loading}
		<div class="state-msg">Loading runs…</div>
	{:else if runs.length === 0}
		<div class="state-msg">
			{fromDate || toDate ? 'No runs in this date range.' : 'No runs ingested yet.'}
		</div>
	{:else}
		<table>
			<colgroup>
				<col style="width: 132px" />
				<col />
				<col style="width: 92px" />
				<col style="width: 84px" />
				<col style="width: 76px" />
				<col style="width: 112px" />
				<col style="width: 72px" />
				<col style="width: 60px" />
			</colgroup>
			<thead>
				<tr>
					<th class="left">date</th>
					<th class="left">name</th>
					<th class="num">distance (mi)</th>
					<th class="num">time</th>
					<th class="num">pace (/mi)</th>
					<th class="num">avg hr</th>
					<th class="num">load</th>
					<th class="num">te</th>
				</tr>
			</thead>
			<tbody>
				{#each runs as run (run.id)}
					{@const hrBadge = hrBadgeLabel(run.hr_source)}
					<tr class="run-row">
						<td class="left date-cell">
							<a class="row-link" href={`/runs/${run.id}`}>
								<span class="date-main">{fmtWeekdayDayMonth(parseIsoDate(run.session_date))}</span>
								<span class="date-sub">{fmtStartTime(run.start_time_local)}</span>
							</a>
						</td>
						<td class="left name-cell">{run.activity_name ?? '—'}</td>
						<td class="num">{fmtMiBare(run.distance_mi)}</td>
						<td class="num">{fmtDuration(run.timer_time_s)}</td>
						<td class="num">{fmtPaceBare(run.pace_min_per_mi)}</td>
						<td class="num">
							{#if run.avg_heart_rate_bpm != null}
								<span class="hr-value">{Math.round(run.avg_heart_rate_bpm)}</span>
								{#if hrBadge}<span class="hr-badge" class:chest={hrBadge === 'CHEST'}>{hrBadge}</span>{/if}
							{:else}
								—
							{/if}
						</td>
						<td class="num">{fmtLoad(run.training_load)}</td>
						<td class="num">{fmtTE(run.aerobic_training_effect)}</td>
					</tr>
				{/each}
			</tbody>
		</table>
	{/if}
</div>

<style>
	.runs-page {
		max-width: 1100px;
		margin: 0 auto;
		padding: 4px 0 24px;
	}

	.page-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 16px;
		margin-bottom: 20px;
	}

	h1 {
		margin: 0;
		font-size: 22px;
		font-weight: 700;
		color: #e8f0f5;
	}

	.filters {
		display: flex;
		align-items: center;
		gap: 12px;
	}

	.filter-field {
		display: flex;
		align-items: center;
		gap: 6px;
		font-family: 'DM Mono', monospace;
		font-size: 11px;
		color: #5e7282;
		text-transform: uppercase;
		letter-spacing: 0.04em;
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

	.clear-btn {
		font-family: 'DM Mono', monospace;
		font-size: 11px;
		letter-spacing: 0.04em;
		text-transform: uppercase;
		color: #8fa3b0;
		padding: 6px 10px;
		border-radius: 6px;
		border: 1px solid rgba(255, 255, 255, 0.08);
		background: transparent;
		cursor: pointer;
		transition: background 0.15s, color 0.15s;
	}
	.clear-btn:hover {
		background: rgba(255, 255, 255, 0.05);
		color: #c3d3dd;
	}

	.error-banner {
		margin-bottom: 16px;
		border-radius: 8px;
		background: rgba(232, 93, 74, 0.1);
		color: #e85d4a;
		padding: 10px 14px;
		font-size: 13px;
	}

	.state-msg {
		padding: 60px 0;
		text-align: center;
		color: #5e7282;
		font-size: 14px;
	}

	table {
		width: 100%;
		border-collapse: collapse;
		font-size: 13px;
	}

	thead th {
		font-weight: 500;
		font-size: 11px;
		color: #5e7282;
		text-transform: uppercase;
		letter-spacing: 0.03em;
		padding: 4px 10px 8px;
		text-align: right;
		border-bottom: 1px solid rgba(255, 255, 255, 0.06);
	}
	thead th.left {
		text-align: left;
	}

	tbody td {
		padding: 9px 10px;
		border-top: 1px solid rgba(255, 255, 255, 0.04);
		vertical-align: middle;
		color: #c3d3dd;
	}

	tr.run-row {
		position: relative;
		transition: background 0.12s;
	}
	tr.run-row:hover {
		background: rgba(255, 255, 255, 0.025);
	}

	/* Stretched-link pattern: the anchor lives in the date cell but is absolutely
	   positioned to cover the whole row (its containing block is the positioned
	   <tr>), so the entire row is a real, keyboard-reachable link without
	   wrapping every cell in markup that breaks table semantics. */
	.row-link {
		position: absolute;
		inset: 0;
		display: flex;
		flex-direction: column;
		justify-content: center;
		padding: 0 10px;
		text-decoration: none;
	}
	.row-link:hover .date-main {
		color: #7ea8d8;
	}

	.date-main {
		display: block;
		color: #e8f0f5;
		font-weight: 500;
		transition: color 0.12s;
	}
	.date-sub {
		display: block;
		margin-top: 1px;
		font-family: 'DM Mono', monospace;
		font-size: 11px;
		color: #5e7282;
	}

	.name-cell {
		color: #a8bac6;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
		max-width: 0;
	}

	.num {
		text-align: right;
		font-family: 'DM Mono', monospace;
		font-variant-numeric: tabular-nums lining-nums;
		white-space: nowrap;
		color: #e8f0f5;
	}

	.hr-value {
		color: #e8f0f5;
	}
	.hr-badge {
		display: inline-block;
		margin-left: 6px;
		padding: 1px 5px;
		border-radius: 3px;
		font-size: 9px;
		font-weight: 500;
		letter-spacing: 0.05em;
		color: #8fa3b0;
		background: rgba(255, 255, 255, 0.06);
		vertical-align: middle;
	}
	.hr-badge.chest {
		color: #5bb5a6;
		background: rgba(91, 181, 166, 0.12);
	}
</style>
