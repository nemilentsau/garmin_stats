<script lang="ts">
	import { onMount, setContext } from 'svelte';
	import {
		api,
		type DailyAggregates,
		type IngestStatus,
		type SyncResult
	} from '$lib/api';
	import { startRealtimePage } from '$lib/realtime-page';
	import { calendarDayDiff, localDateIso, parseIsoDate, fmtFullDate } from '$lib/date';
	import { createRefreshBus, DASHBOARD_REFRESH } from '$lib/dashboard/refresh-bus';
	import RecoverySection from '$lib/components/recovery/RecoverySection.svelte';

	let data: DailyAggregates | null = $state(null);
	let ingestStatus: IngestStatus | null = $state(null);
	let emptyState: IngestStatus | null = $state(null);
	let error: string | null = $state(null);
	let syncing = $state(false);
	let syncResult = $state<SyncResult | null>(null);

	// One refresh bus for the whole overview; axis sections subscribe to re-fetch on
	// realtime/sync. setContext must run during component init (here), not in onMount.
	const bus = createRefreshBus();
	setContext(DASHBOARD_REFRESH, bus);

	async function fetchData() {
		error = null;
		const status = await api.getIngestStatus();
		ingestStatus = status;
		if (status.days_in_db === 0) {
			data = null;
			emptyState = status;
			return;
		}
		data = await api.getDailyAggregates();
		emptyState = null;
		bus.emit(); // tell mounted axis sections the data changed
	}

	function formatBannerDate(date: string): string {
		return fmtFullDate(parseIsoDate(date));
	}

	onMount(() => {
		return startRealtimePage({
			fetchData,
			setError: (message) => {
				error = message;
			},
			setLoading: () => {}
		});
	});

	const latestIngestedDate = $derived.by(() => data?.days[data.days.length - 1] ?? null);

	const freshnessNotice = $derived.by(() => {
		if (!ingestStatus || ingestStatus.days_in_db === 0 || !latestIngestedDate) return null;
		const today = localDateIso();
		const daysBehind = calendarDayDiff(latestIngestedDate, today);
		if (daysBehind > 0) {
			return {
				tone: 'stale' as const,
				headline: `Garmin data is ${daysBehind} ${daysBehind === 1 ? 'day' : 'days'} behind the laptop date.`,
				detail: `Data is current through ${formatBannerDate(latestIngestedDate)}. This laptop is on ${formatBannerDate(today)}. Update exports before trusting current-day planning or experiment context.`
			};
		}
		if (ingestStatus.needs_ingest) {
			return {
				tone: 'pending' as const,
				headline: 'New Garmin files are waiting to ingest.',
				detail: `Current data is through ${formatBannerDate(latestIngestedDate)}. Run an ingest after the next device sync if you need the newest recovery signals.`
			};
		}
		return null;
	});

	async function handleSync(): Promise<void> {
		if (syncing) return;
		syncing = true;
		syncResult = null;
		error = null;
		try {
			syncResult = await api.triggerSync();
			await fetchData();
		} catch (e: unknown) {
			error = e instanceof Error ? e.message : String(e);
		} finally {
			syncing = false;
		}
	}
</script>

<svelte:head>
	<title>Dashboard - Garmin Stats</title>
</svelte:head>

{#if error && !data}
	<div class="topo-error">
		<p>Error: {error}</p>
	</div>
{:else if emptyState}
	<section class="empty-shell">
		<div class="empty-welcome">
			<div class="empty-icon">
				<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
					<path d="M22 12h-4l-3 9L9 3l-3 9H2" />
				</svg>
			</div>
			<div class="empty-text">
				<h2>Waiting for Garmin data</h2>
				<p>
					{#if emptyState.days_on_disk === 0}
						Drop <code>.zip</code> archives into <code>data/garmin_health_stats/</code> to get started.
					{:else}
						{emptyState.days_on_disk} {emptyState.days_on_disk === 1 ? 'day' : 'days'} found on disk — trigger an ingest to build the dashboard.
					{/if}
				</p>
			</div>
		</div>

		<div class="empty-steps">
			<div class="empty-step" class:done={emptyState.days_on_disk > 0}>
				<div class="step-marker">{emptyState.days_on_disk > 0 ? '✓' : '1'}</div>
				<div class="step-body">
					<span class="step-title">Add export archives</span>
					<span class="step-desc">Place Garmin <code>YYYY-MM-DD.zip</code> files in the data directory</span>
				</div>
			</div>
			<div class="step-connector"></div>
			<div class="empty-step">
				<div class="step-marker">2</div>
				<div class="step-body">
					<span class="step-title">Ingest</span>
					<span class="step-desc">POST to <code>/api/ingest</code> or wait for the watcher to pick them up</span>
				</div>
			</div>
			<div class="step-connector"></div>
			<div class="empty-step">
				<div class="step-marker">3</div>
				<div class="step-body">
					<span class="step-title">Dashboard populates</span>
					<span class="step-desc">Recovery scores, vitals, and trends appear automatically</span>
				</div>
			</div>
		</div>
	</section>
{:else if !data}
	<div class="topo-loading">
		<div class="loading-pulse"></div>
		<span>Mapping terrain data...</span>
	</div>
{:else}
	{#if error}
		<div class="inline-error-banner">
			<span>Error: {error}</span>
			<button type="button" class="inline-error-dismiss" onclick={() => (error = null)} aria-label="Dismiss error">✕</button>
		</div>
	{/if}
	{#if freshnessNotice}
		<section class:pending={freshnessNotice.tone === 'pending'} class="freshness-banner">
			<div class="freshness-label">Data freshness</div>
			<div class="freshness-copy">
				<strong>{freshnessNotice.headline}</strong>
				<p>{freshnessNotice.detail}</p>
			</div>
			<button class="sync-btn" onclick={handleSync} disabled={syncing}>
				{#if syncing}
					<span class="sync-spinner"></span> Syncing…
				{:else}
					Sync Garmin
				{/if}
			</button>
		</section>
	{:else if ingestStatus && ingestStatus.days_in_db > 0}
		<div class="sync-bar">
			<button class="sync-btn compact" onclick={handleSync} disabled={syncing}>
				{#if syncing}
					<span class="sync-spinner"></span> Syncing…
				{:else}
					Sync Garmin
				{/if}
			</button>
			{#if syncResult}
				<span class="sync-result">
					{syncResult.downloaded} archives, {syncResult.activities_downloaded} workouts, {syncResult.days_ingested} days ingested
				</span>
			{/if}
		</div>
	{/if}
	{#if syncResult && freshnessNotice}
		<div class="sync-result-banner">
			{syncResult.downloaded} archives, {syncResult.activities_downloaded} workouts, {syncResult.days_ingested} days ingested
		</div>
	{/if}

		<RecoverySection />

{/if}

<style>
	.topo-error {
		margin: 40px 0;
		padding: 20px;
		border: 1px solid rgba(232,93,74,0.3);
		border-radius: 8px;
		background: rgba(232,93,74,0.08);
		color: #E85D4A;
		font-family: 'DM Mono', monospace;
		font-size: 13px;
	}

	/* ── Inline, dismissible refresh/sync error — used instead of `.topo-error` once the
	     dashboard already has data on screen, so a transient background-refresh failure
	     doesn't blank a fully-loaded page (keep-last-good, same spirit as RecoverySection). ── */
	.inline-error-banner {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 12px;
		margin: 0 0 18px;
		padding: 10px 14px;
		border: 1px solid rgba(232,93,74,0.3);
		border-radius: 8px;
		background: rgba(232,93,74,0.08);
		color: #E85D4A;
		font-family: 'DM Mono', monospace;
		font-size: 13px;
	}
	.inline-error-dismiss {
		flex-shrink: 0;
		border: 0;
		background: transparent;
		color: inherit;
		font-size: 12px;
		line-height: 1;
		padding: 2px 4px;
		cursor: pointer;
		opacity: 0.7;
	}
	.inline-error-dismiss:hover {
		opacity: 1;
	}

	.topo-loading {
		display: flex;
		align-items: center;
		justify-content: center;
		gap: 12px;
		height: 60vh;
		font-family: 'DM Mono', monospace;
		font-size: 13px;
		color: #5e7282;
	}

	.loading-pulse {
		width: 8px;
		height: 8px;
		border-radius: 50%;
		background: #5BB5A6;
		animation: pulse 1.5s ease-in-out infinite;
	}

	@keyframes pulse {
		0%, 100% { opacity: 0.3; transform: scale(0.8); }
		50% { opacity: 1; transform: scale(1.2); }
	}

	.empty-shell {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 32px;
		padding: 48px 0 24px;
		max-width: 520px;
		margin: 0 auto;
	}

	.empty-welcome {
		display: flex;
		align-items: center;
		gap: 16px;
	}

	.empty-icon {
		width: 44px;
		height: 44px;
		flex-shrink: 0;
		display: flex;
		align-items: center;
		justify-content: center;
		border-radius: 12px;
		background: rgba(91,181,166,0.10);
		color: #5BB5A6;
	}

	.empty-icon svg {
		width: 22px;
		height: 22px;
	}

	.empty-text h2 {
		margin: 0;
		font-size: 18px;
		font-weight: 600;
		color: #e0eaf0;
		letter-spacing: -0.01em;
	}

	.empty-text p {
		margin: 4px 0 0;
		font-size: 13px;
		color: #7e8f9e;
		line-height: 1.5;
	}

	.empty-text code {
		font-family: 'DM Mono', monospace;
		font-size: 12px;
		color: #a0b8c8;
		background: rgba(255,255,255,0.05);
		padding: 1px 5px;
		border-radius: 4px;
	}

	.empty-steps {
		display: flex;
		flex-direction: column;
		gap: 0;
		width: 100%;
		padding: 20px 24px;
		border: 1px solid rgba(255,255,255,0.06);
		border-radius: 14px;
		background: rgba(255,255,255,0.02);
	}

	.empty-step {
		display: flex;
		align-items: flex-start;
		gap: 14px;
		padding: 10px 0;
	}

	.step-marker {
		width: 28px;
		height: 28px;
		flex-shrink: 0;
		display: flex;
		align-items: center;
		justify-content: center;
		border-radius: 8px;
		background: rgba(255,255,255,0.04);
		border: 1px solid rgba(255,255,255,0.08);
		font-family: 'DM Mono', monospace;
		font-size: 12px;
		color: #6b7d8e;
		font-weight: 500;
	}

	.empty-step.done .step-marker {
		background: rgba(91,181,166,0.14);
		border-color: rgba(91,181,166,0.25);
		color: #5BB5A6;
	}

	.step-connector {
		width: 1px;
		height: 12px;
		margin-left: 13.5px;
		background: rgba(255,255,255,0.06);
	}

	.step-body {
		display: flex;
		flex-direction: column;
		gap: 2px;
		padding-top: 4px;
	}

	.step-title {
		font-size: 13px;
		font-weight: 500;
		color: #c8d6e0;
	}

	.step-desc {
		font-size: 12px;
		color: #6b7d8e;
		line-height: 1.45;
	}

	.step-desc code {
		font-family: 'DM Mono', monospace;
		font-size: 11px;
		color: #8fa3b0;
	}

	.freshness-banner {
		display: grid;
		grid-template-columns: auto 1fr auto;
		gap: 14px;
		align-items: center;
		margin: 0 0 18px;
		padding: 14px 16px;
		border: 1px solid rgba(228,164,72,0.28);
		border-radius: 16px;
		background:
			linear-gradient(135deg, rgba(228,164,72,0.16), rgba(228,93,74,0.08)),
			rgba(255,255,255,0.03);
		box-shadow: 0 18px 36px rgba(0,0,0,0.16);
	}

	.freshness-banner.pending {
		border-color: rgba(91,181,166,0.24);
		background:
			linear-gradient(135deg, rgba(91,181,166,0.14), rgba(74,144,217,0.08)),
			rgba(255,255,255,0.03);
	}

	.freshness-label {
		padding: 5px 8px;
		border-radius: 999px;
		background: rgba(255,255,255,0.08);
		color: #f3c47b;
		font-family: 'DM Mono', monospace;
		font-size: 10px;
		letter-spacing: 0.14em;
		text-transform: uppercase;
	}

	.freshness-banner.pending .freshness-label {
		color: #7fc9bc;
	}

	.freshness-copy {
		display: grid;
		gap: 4px;
	}

	.freshness-copy strong {
		font-size: 14px;
		line-height: 1.35;
		color: #f4f7f9;
	}

	.freshness-copy p {
		margin: 0;
		font-size: 13px;
		line-height: 1.55;
		color: #b7c5cf;
	}

	.sync-btn {
		align-self: center;
		padding: 7px 16px;
		border: 1px solid rgba(255,255,255,0.12);
		border-radius: 8px;
		background: rgba(255,255,255,0.06);
		color: #d0dce4;
		font-family: 'DM Sans', sans-serif;
		font-size: 13px;
		font-weight: 500;
		cursor: pointer;
		white-space: nowrap;
		transition: background 0.15s, border-color 0.15s;
		display: flex;
		align-items: center;
		gap: 6px;
	}

	.sync-btn:hover:not(:disabled) {
		background: rgba(255,255,255,0.10);
		border-color: rgba(255,255,255,0.20);
	}

	.sync-btn:disabled {
		opacity: 0.6;
		cursor: not-allowed;
	}

	.sync-btn.compact {
		padding: 5px 12px;
		font-size: 12px;
	}

	.sync-spinner {
		display: inline-block;
		width: 12px;
		height: 12px;
		border: 2px solid rgba(255,255,255,0.2);
		border-top-color: #d0dce4;
		border-radius: 50%;
		animation: spin 0.8s linear infinite;
	}

	@keyframes spin {
		to { transform: rotate(360deg); }
	}

	.sync-bar {
		display: flex;
		align-items: center;
		gap: 12px;
		margin: 0 0 18px;
		justify-content: flex-end;
	}

	.sync-result,
	.sync-result-banner {
		font-size: 12px;
		color: #7fc9bc;
		font-family: 'DM Mono', monospace;
	}

	.sync-result-banner {
		margin: -10px 0 14px;
		text-align: right;
	}

	@media (max-width: 900px) {
		.freshness-banner {
			grid-template-columns: 1fr;
		}
	}

</style>
