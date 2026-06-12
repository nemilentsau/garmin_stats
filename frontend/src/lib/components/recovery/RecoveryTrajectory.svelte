<script lang="ts">
	import type { ChartConfiguration } from 'chart.js';
	import type { DashboardOverview } from '$lib/api';
	import LineChart from '$lib/components/LineChart.svelte';
	import { DARK_BORDER, DARK_GRID_Y, DARK_TICK, chartTooltip } from '$lib/chart-setup';

	let {
		score,
		change
	}: {
		score: DashboardOverview['score'];
		change: DashboardOverview['change'];
	} = $props();

	const RANGES = [
		{ key: '7d', days: 7 },
		{ key: '30d', days: 30 },
		{ key: '90d', days: 90 }
	] as const;
	let rangeKey = $state<'7d' | '30d' | '90d'>('90d');

	const SCORE_COLOR = '#7ea8d8';
	const RAW_COLOR = 'rgba(255,255,255,0.16)';
	const BAND_FILL = 'rgba(126,168,216,0.06)';

	const windowed = $derived.by(() => {
		const days = RANGES.find((r) => r.key === rangeKey)?.days ?? 90;
		return score.slice(Math.max(0, score.length - days));
	});

	const config = $derived.by<ChartConfiguration<'line'>>(() => {
		const labels = windowed.map((p) => p.date);
		return {
			type: 'line',
			data: {
				labels,
				datasets: [
					{
						label: 'daily',
						data: windowed.map((p) => p.raw),
						borderColor: RAW_COLOR,
						borderWidth: 1,
						pointRadius: 0,
						tension: 0.2,
						spanGaps: false
					},
					{
						label: '7-day average',
						data: windowed.map((p) => p.ma7),
						borderColor: SCORE_COLOR,
						borderWidth: 2,
						pointRadius: 0,
						tension: 0.3,
						spanGaps: false
					}
				]
			},
			options: {
				responsive: true,
				maintainAspectRatio: false,
				interaction: { mode: 'index', intersect: false },
				scales: {
					x: {
						type: 'time',
						time: { unit: rangeKey === '7d' ? 'day' : 'month' },
						grid: { display: false },
						border: DARK_BORDER,
						ticks: { color: DARK_TICK.color, maxRotation: 0, autoSkipPadding: 24 }
					},
					y: {
						grid: DARK_GRID_Y,
						border: { display: false },
						ticks: { color: DARK_TICK.color, stepSize: 1 },
						title: { display: true, text: 'recovery (z vs your baseline)', color: '#5e7282', font: { size: 11 } }
					}
				},
				plugins: {
					legend: { display: false },
					tooltip: {
						...chartTooltip(SCORE_COLOR),
						callbacks: {
							title: (items) =>
								new Intl.DateTimeFormat('en-US', {
									month: 'short',
									day: 'numeric',
									year: 'numeric'
								}).format(new Date(items[0].parsed.x ?? 0)),
							label: (item) =>
								`${item.dataset.label}: ${item.parsed.y == null ? '—' : item.parsed.y.toFixed(2)} z`
						}
					},
					annotation: {
						annotations: {
							typicalBand: {
								type: 'box',
								yMin: -0.5,
								yMax: 0.5,
								backgroundColor: BAND_FILL,
								borderWidth: 0,
								label: {
									display: true,
									content: 'typical',
									position: { x: 'start', y: 'center' },
									color: '#5e7282',
									font: { size: 10 },
									backgroundColor: 'transparent'
								}
							},
							zeroLine: {
								type: 'line',
								yMin: 0,
								yMax: 0,
								borderColor: 'rgba(255,255,255,0.10)',
								borderWidth: 1
							}
						}
					}
				}
			}
		};
	});

	const subtitle = $derived(
		change.is_meaningful && change.direction
			? `7-day avg ${change.direction} vs prior week (Δ ${change.delta7_z?.toFixed(1)} z)`
			: '7-day average · change within normal range'
	);
</script>

<section class="trajectory">
	<header>
		<div class="titles">
			<h2>Recovery trajectory</h2>
			<span class="subtitle">{subtitle}</span>
		</div>
		<div class="ranges" role="group" aria-label="time range">
			{#each RANGES as r}
				<button class:active={rangeKey === r.key} onclick={() => (rangeKey = r.key)}>{r.key}</button>
			{/each}
		</div>
	</header>
	<div class="chart">
		<LineChart {config} height={260} />
	</div>
</section>

<style>
	.trajectory {
		padding: 18px 0;
	}
	header {
		display: flex;
		align-items: flex-start;
		justify-content: space-between;
		gap: 16px;
		margin-bottom: 8px;
	}
	.titles {
		display: flex;
		flex-direction: column;
		gap: 2px;
	}
	h2 {
		font-size: 13px;
		font-weight: 600;
		color: #c8d6e0;
		margin: 0;
		text-transform: uppercase;
		letter-spacing: 0.04em;
	}
	.subtitle {
		font-size: 12px;
		color: #5e7282;
	}
	.ranges {
		display: flex;
		gap: 2px;
	}
	.ranges button {
		font-family: 'DM Mono', monospace;
		font-size: 11px;
		color: #8a9baa;
		background: transparent;
		border: 1px solid rgba(255, 255, 255, 0.08);
		padding: 3px 8px;
		cursor: pointer;
		border-radius: 4px;
	}
	.ranges button.active {
		color: #e8f0f5;
		background: rgba(126, 168, 216, 0.12);
		border-color: rgba(126, 168, 216, 0.4);
	}
	.chart {
		position: relative;
	}
</style>
