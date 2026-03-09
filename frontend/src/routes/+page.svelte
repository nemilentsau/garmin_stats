<script lang="ts">
	import { onMount } from 'svelte';
	import { api, type DailyAggregates, type DashboardOverview } from '$lib/api';
	import { startRealtimePage } from '$lib/realtime-page';
	import { Chart, DARK_BORDER } from '$lib/chart-setup';
	import type { ChartConfiguration } from 'chart.js';
	import { fmt, fmtSigned } from '$lib/format';
	import { COLORS } from '$lib/colors';

	let data: DailyAggregates | null = $state(null);
	let overview: DashboardOverview | null = $state(null);
	let error: string | null = $state(null);
	let sparkCanvases: Record<string, HTMLCanvasElement> = $state({});
	let sparkCharts: Record<string, Chart<'line'>> = {};

	async function fetchData() {
		const [nextData, nextOverview] = await Promise.all([
			api.getDailyAggregates(),
			api.getDashboardOverview()
		]);
		data = nextData;
		overview = nextOverview;
	}

	onMount(() => {
		return startRealtimePage({
			fetchData,
			setError: (message) => { error = message; },
			setLoading: () => {}
		});
	});

	function readinessColor(score: number | null | undefined): string {
		if (score == null) return '#8a9baa';
		if (score >= 75) return COLORS.heartRateResting;
		if (score >= 50) return COLORS.stress;
		return COLORS.heartRate;
	}

	type ReadinessComponent = {
		label: string;
		color: string;
		description: string;
	};

	const componentInfo: Record<string, ReadinessComponent> = {
		hrv_recovery: {
			label: 'HRV Recovery',
			color: COLORS.hrv,
			description: 'Overnight HRV trend vs your recent baseline'
		},
		sleep: {
			label: 'Sleep',
			color: COLORS.sleep,
			description: 'Sleep quality score from last night'
		},
		resting_hr: {
			label: 'Resting HR',
			color: COLORS.heartRate,
			description: 'Resting heart rate change vs 7-day average'
		},
		hrv_status: {
			label: 'HRV Status',
			color: COLORS.respiration,
			description: 'Autonomic nervous system balance assessment'
		}
	};

	const componentOrder = ['hrv_recovery', 'sleep', 'resting_hr', 'hrv_status'] as const;

	// ── Vitals KPI config ──
	type VitalConfig = {
		key: string;
		label: string;
		unit: string;
		color: string;
		getValue: (v: NonNullable<DashboardOverview['vitals']>) => number | null | undefined;
		getDelta: (v: NonNullable<DashboardOverview['vitals']>) => number | null | undefined;
		lowerIsBetter: boolean;
	};

	const vitalConfigs: VitalConfig[] = [
		{
			key: 'resting_hr',
			label: 'Resting HR',
			unit: 'bpm',
			color: COLORS.heartRate,
			getValue: (v) => v.resting_hr,
			getDelta: (v) => v.resting_hr_delta_7d,
			lowerIsBetter: true
		},
		{
			key: 'nightly_hrv',
			label: 'Nightly HRV',
			unit: 'ms',
			color: COLORS.hrv,
			getValue: (v) => v.nightly_hrv,
			getDelta: (v) => v.nightly_hrv_delta_7d,
			lowerIsBetter: false
		},
		{
			key: 'sleep_score',
			label: 'Sleep Score',
			unit: 'pts',
			color: COLORS.sleep,
			getValue: (v) => v.sleep_score,
			getDelta: () => null,
			lowerIsBetter: false
		},
		{
			key: 'stress_avg',
			label: 'Stress',
			unit: 'avg',
			color: COLORS.stress,
			getValue: (v) => v.stress_avg,
			getDelta: () => null,
			lowerIsBetter: true
		}
	];

	function deltaColor(delta: number | null | undefined, lowerIsBetter: boolean): string {
		if (delta == null) return '#5e7282';
		const isGood = lowerIsBetter ? delta < 0 : delta > 0;
		if (isGood) return COLORS.heartRateResting;
		if (delta === 0) return '#5e7282';
		return COLORS.heartRate;
	}

	// ── Sparkline configs ──
	type SparkConfig = {
		key: string;
		label: string;
		color: string;
		getData: (s: NonNullable<DashboardOverview['sparklines']>) => Array<{ date: string; value: number | null }>;
	};

	const sparkConfigs: SparkConfig[] = [
		{ key: 'resting_hr', label: 'Resting HR', color: COLORS.heartRate, getData: (s) => s.resting_hr },
		{ key: 'nightly_hrv', label: 'Nightly HRV', color: COLORS.hrv, getData: (s) => s.nightly_hrv },
		{ key: 'sleep_score', label: 'Sleep Score', color: COLORS.sleep, getData: (s) => s.sleep_score },
		{ key: 'stress_avg', label: 'Stress', color: COLORS.stress, getData: (s) => s.stress_avg }
	];

	function createSparkline(canvas: HTMLCanvasElement, points: Array<{ value: number | null }>, color: string): Chart<'line'> {
		const config: ChartConfiguration<'line'> = {
			type: 'line',
			data: {
				labels: points.map((_, i) => String(i)),
				datasets: [{
					data: points.map((p) => p.value),
					borderColor: color,
					backgroundColor: color + '15',
					borderWidth: 1.5,
					pointRadius: 0,
					pointHoverRadius: 0,
					tension: 0.4,
					spanGaps: true,
					fill: true
				}]
			},
			options: {
				responsive: true,
				maintainAspectRatio: false,
				plugins: { legend: { display: false }, tooltip: { enabled: false } },
				scales: {
					x: { display: false, border: DARK_BORDER },
					y: { display: false, border: DARK_BORDER }
				},
				animation: false,
				events: []
			}
		};
		return new Chart(canvas, config);
	}

	$effect(() => {
		if (!overview?.sparklines) return;
		const sparklines = overview.sparklines;
		for (const sc of sparkConfigs) {
			const canvas = sparkCanvases[sc.key];
			if (!canvas) continue;
			const points = sc.getData(sparklines);
			if (sparkCharts[sc.key]) {
				const chart = sparkCharts[sc.key];
				chart.data.labels = points.map((_, i) => String(i));
				chart.data.datasets[0].data = points.map((p) => p.value);
				chart.update();
			} else {
				sparkCharts[sc.key] = createSparkline(canvas, points, sc.color);
			}
		}
	});

	onMount(() => {
		return () => {
			Object.values(sparkCharts).forEach((c) => c.destroy());
		};
	});
</script>

<svelte:head>
	<title>Dashboard - Garmin Stats</title>
</svelte:head>

{#if error}
	<div class="topo-error">
		<p>Error: {error}</p>
	</div>
{:else if !data}
	<div class="topo-loading">
		<div class="loading-pulse"></div>
		<span>Mapping terrain data...</span>
	</div>
{:else}
	<!-- Readiness hero -->
	{#if overview?.readiness}
		{@const r = overview.readiness}
		<div class="readiness-hero">
			<div class="readiness-top">
				<div class="readiness-ring" style="--ring-color:{readinessColor(r.score)}; --ring-pct:{r.score ?? 0}">
					<svg viewBox="0 0 120 120" class="ring-svg">
						<circle cx="60" cy="60" r="52" class="ring-track" />
						<circle cx="60" cy="60" r="52" class="ring-fill" style="stroke:{readinessColor(r.score)}; stroke-dasharray:{((r.score ?? 0) / 100) * 327} 327" />
					</svg>
					<div class="ring-content">
						<span class="ring-score" style="color:{readinessColor(r.score)}">{r.score ?? '-'}</span>
					</div>
				</div>
				<div class="readiness-info">
					<span class="readiness-label" style="color:{readinessColor(r.score)}">{r.label ?? '-'}</span>
					<span class="readiness-subtitle">Readiness · {overview.date}</span>
					<p class="readiness-explain">
						Composite score from 4 recovery signals, each contributing up to 25 points.
					</p>
				</div>
			</div>
			<div class="readiness-components">
				{#each componentOrder as key}
					{@const val = r.components[key] ?? 0}
					{@const info = componentInfo[key]}
					{@const vitals = overview?.vitals}
					<div class="comp-row">
						<div class="comp-header">
							<div class="comp-dot" style="background:{info.color}"></div>
							<span class="comp-label">{info.label}</span>
							{#if key === 'hrv_recovery' && vitals?.nightly_hrv != null}
								<span class="comp-actual">{fmt(vitals.nightly_hrv)} ms</span>
								{#if vitals.nightly_hrv_delta_7d != null}
									<span class="comp-delta" style="color:{deltaColor(vitals.nightly_hrv_delta_7d, false)}">{fmtSigned(vitals.nightly_hrv_delta_7d)}</span>
								{/if}
							{:else if key === 'sleep' && vitals?.sleep_score != null}
								<span class="comp-actual">{vitals.sleep_score} pts</span>
							{:else if key === 'resting_hr' && vitals?.resting_hr != null}
								<span class="comp-actual">{vitals.resting_hr} bpm</span>
								{#if vitals.resting_hr_delta_7d != null}
									<span class="comp-delta" style="color:{deltaColor(vitals.resting_hr_delta_7d, true)}">{fmtSigned(vitals.resting_hr_delta_7d)}</span>
								{/if}
							{:else if key === 'hrv_status' && vitals?.hrv_status}
								<span class="comp-actual">{vitals.hrv_status}</span>
							{/if}
							<span class="comp-score" style="color:{info.color}">{Math.round(val)}</span>
							<span class="comp-max">/ 25</span>
						</div>
						<div class="comp-bar-track">
							<div class="comp-bar-fill" style="width:{(val / 25) * 100}%; background:{info.color}"></div>
						</div>
					</div>
				{/each}
			</div>
		</div>
	{/if}

	<!-- Today's Vitals -->
	{#if overview?.vitals}
		{@const vitals = overview.vitals}
		<div class="vitals-row">
			{#each vitalConfigs as vc}
				{@const val = vc.getValue(vitals)}
				{@const delta = vc.getDelta(vitals)}
				<div class="vital-item">
					<span class="vital-label">{vc.label}</span>
					<div class="vital-value-row">
						<span class="vital-value" style="color:{vc.color}">{fmt(val)}</span>
						<span class="vital-unit">{vc.unit}</span>
					</div>
					{#if delta != null}
						<span class="vital-delta" style="color:{deltaColor(delta, vc.lowerIsBetter)}">{fmtSigned(delta)} vs 7d</span>
					{/if}
				</div>
			{/each}
		</div>
	{/if}

	<!-- 3-Month Sparklines -->
	{#if overview?.sparklines}
		<div class="sparkline-grid">
			{#each sparkConfigs as sc}
				<div class="sparkline-card">
					<span class="sparkline-label">{sc.label}</span>
					<div class="sparkline-chart">
						<canvas bind:this={sparkCanvases[sc.key]}></canvas>
					</div>
				</div>
			{/each}
		</div>
	{/if}

	<!-- Data info line -->
	<div class="data-info">
		{data.days.length} days collected &mdash; {data.days[0]} to {data.days[data.days.length - 1]}
	</div>
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

	/* Readiness hero */
	.readiness-hero {
		background: rgba(255,255,255,0.02);
		border: 1px solid rgba(255,255,255,0.05);
		border-radius: 10px;
		padding: 28px;
		margin-bottom: 20px;
	}

	.readiness-top {
		display: flex;
		align-items: center;
		gap: 24px;
		margin-bottom: 24px;
		padding-bottom: 20px;
		border-bottom: 1px solid rgba(255,255,255,0.04);
	}

	.readiness-ring {
		position: relative;
		width: 100px;
		height: 100px;
		flex-shrink: 0;
	}

	.ring-svg {
		width: 100%;
		height: 100%;
		transform: rotate(-90deg);
	}

	.ring-track {
		fill: none;
		stroke: rgba(255,255,255,0.05);
		stroke-width: 6;
	}

	.ring-fill {
		fill: none;
		stroke-width: 6;
		stroke-linecap: round;
		transition: stroke-dasharray 0.6s ease;
	}

	.ring-content {
		position: absolute;
		inset: 0;
		display: flex;
		align-items: center;
		justify-content: center;
	}

	.ring-score {
		font-family: 'DM Mono', monospace;
		font-size: 32px;
		font-weight: 600;
		line-height: 1;
	}

	.readiness-info {
		display: flex;
		flex-direction: column;
		gap: 4px;
	}

	.readiness-label {
		font-family: 'DM Mono', monospace;
		font-size: 16px;
		font-weight: 600;
		letter-spacing: 2px;
		text-transform: uppercase;
	}

	.readiness-subtitle {
		font-size: 11px;
		color: #5e7282;
	}

	.readiness-explain {
		font-size: 11px;
		color: #4a5c6a;
		margin: 4px 0 0;
		line-height: 1.4;
	}

	.readiness-components {
		display: grid;
		grid-template-columns: repeat(2, 1fr);
		gap: 16px;
	}

	.comp-row {
		display: flex;
		flex-direction: column;
		gap: 6px;
	}

	.comp-header {
		display: flex;
		align-items: center;
		gap: 6px;
	}

	.comp-dot {
		width: 6px;
		height: 6px;
		border-radius: 50%;
		flex-shrink: 0;
	}

	.comp-label {
		font-size: 11px;
		color: #8a9baa;
		letter-spacing: 0.5px;
		font-weight: 500;
	}

	.comp-actual {
		font-family: 'DM Mono', monospace;
		font-size: 11px;
		color: #c8d6e0;
		margin-left: 4px;
	}

	.comp-delta {
		font-family: 'DM Mono', monospace;
		font-size: 10px;
	}

	.comp-score {
		font-family: 'DM Mono', monospace;
		font-size: 13px;
		font-weight: 600;
		margin-left: auto;
	}

	.comp-max {
		font-family: 'DM Mono', monospace;
		font-size: 10px;
		color: #3a4a56;
	}

	.comp-bar-track {
		height: 4px;
		background: rgba(255,255,255,0.05);
		border-radius: 2px;
		overflow: hidden;
	}

	.comp-bar-fill {
		height: 100%;
		border-radius: 2px;
		transition: width 0.5s ease;
		opacity: 0.8;
	}

	/* Today's Vitals */
	.vitals-row {
		display: flex;
		justify-content: space-between;
		gap: 1px;
		background: rgba(255,255,255,0.06);
		border-radius: 10px;
		overflow: hidden;
		margin-bottom: 20px;
	}

	.vital-item {
		flex: 1;
		background: rgba(13,21,32,0.95);
		padding: 16px 20px;
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 4px;
	}

	.vital-label {
		font-size: 9px;
		letter-spacing: 1.5px;
		text-transform: uppercase;
		color: #5e7282;
	}

	.vital-value-row {
		display: flex;
		align-items: baseline;
		gap: 4px;
	}

	.vital-value {
		font-family: 'DM Mono', monospace;
		font-size: 24px;
		font-weight: 500;
		line-height: 1;
	}

	.vital-unit {
		font-family: 'DM Mono', monospace;
		font-size: 9px;
		color: #4a5c6a;
		letter-spacing: 1px;
	}

	.vital-delta {
		font-family: 'DM Mono', monospace;
		font-size: 10px;
	}

	/* Sparkline grid */
	.sparkline-grid {
		display: grid;
		grid-template-columns: repeat(4, 1fr);
		gap: 12px;
		margin-bottom: 20px;
	}

	.sparkline-card {
		background: rgba(255,255,255,0.02);
		border: 1px solid rgba(255,255,255,0.05);
		border-radius: 10px;
		padding: 12px 14px;
	}

	.sparkline-label {
		font-size: 9px;
		letter-spacing: 1.5px;
		text-transform: uppercase;
		color: #5e7282;
		display: block;
		margin-bottom: 6px;
	}

	.sparkline-chart {
		height: 40px;
		position: relative;
	}

	/* Data info line */
	.data-info {
		font-family: 'DM Mono', monospace;
		font-size: 10px;
		color: #4a5c6a;
		letter-spacing: 2px;
		text-transform: uppercase;
		text-align: center;
		padding: 8px 0;
	}

	@media (max-width: 768px) {
		.vitals-row { flex-wrap: wrap; }
		.vital-item { min-width: 45%; }
		.sparkline-grid { grid-template-columns: repeat(2, 1fr); }
		.readiness-components { grid-template-columns: 1fr; }
		.readiness-top { flex-direction: column; text-align: center; }
	}
</style>
