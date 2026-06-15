<script lang="ts">
	import { onMount, getContext } from 'svelte';
	import { api, type DashboardOverview } from '$lib/api';
	import { DASHBOARD_REFRESH, type RefreshBus } from '$lib/dashboard/refresh-bus';
	import StateLine from './StateLine.svelte';
	import RecoveryTrajectory from './RecoveryTrajectory.svelte';
	import EvidenceTable from './EvidenceTable.svelte';
	import FlagStrip from './FlagStrip.svelte';

	// getContext must run during component init (not inside onMount). The shell always
	// provides the bus; `?.` guards the (unsupported) case of mounting outside the shell.
	const bus = getContext<RefreshBus | undefined>(DASHBOARD_REFRESH);

	let overview = $state<DashboardOverview | null>(null);
	let error = $state<string | null>(null);
	let hoveredDate = $state<string | null>(null);

	async function load(): Promise<void> {
		try {
			overview = await api.getDashboardOverview();
			hoveredDate = null; // drop any brushed day when the data reloads
			error = null;
		} catch (e: unknown) {
			// Keep the last good data on a failed background reload; only surface the
			// error when we have nothing to show (the initial load failed). The next
			// successful refresh clears it.
			if (!overview) error = e instanceof Error ? e.message : String(e);
		}
	}

	onMount(() => {
		void load();
		return bus?.subscribe(() => void load());
	});
</script>

{#if error}
	<div class="section-error">Error: {error}</div>
{:else if !overview}
	<div class="section-loading">
		<div class="loading-pulse"></div>
		<span>Loading recovery…</span>
	</div>
{:else}
	<StateLine state={overview.state} date={overview.date} />
	<RecoveryTrajectory
		score={overview.score}
		change={overview.change}
		events={overview.events}
		onHoverDate={(d) => (hoveredDate = d)}
	/>
	<EvidenceTable
		evidence={overview.evidence}
		driverSeries={overview.driver_series}
		dates={overview.score.map((p) => p.date)}
		{hoveredDate}
	/>
	<FlagStrip
		flags={overview.flags}
		flagSeries={overview.flag_series}
		latestDate={overview.date}
		{hoveredDate}
	/>
{/if}

<style>
	.section-error {
		margin: 24px 0;
		padding: 16px;
		border: 1px solid rgba(232, 93, 74, 0.3);
		border-radius: 8px;
		background: rgba(232, 93, 74, 0.08);
		color: #e85d4a;
		font-family: 'DM Mono', monospace;
		font-size: 13px;
	}

	.section-loading {
		display: flex;
		align-items: center;
		justify-content: center;
		gap: 12px;
		height: 40vh;
		font-family: 'DM Mono', monospace;
		font-size: 13px;
		color: #5e7282;
	}

	.loading-pulse {
		width: 8px;
		height: 8px;
		border-radius: 50%;
		background: #5bb5a6;
		animation: pulse 1.5s ease-in-out infinite;
	}

	@keyframes pulse {
		0%,
		100% {
			opacity: 0.3;
			transform: scale(0.8);
		}
		50% {
			opacity: 1;
			transform: scale(1.2);
		}
	}
</style>
