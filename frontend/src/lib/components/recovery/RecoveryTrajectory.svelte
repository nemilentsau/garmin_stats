<script lang="ts">
	import type { ChartConfiguration } from 'chart.js';
	import type { DashboardOverview } from '$lib/api';
	import LineChart from '$lib/components/LineChart.svelte';
	import { DARK_BORDER, DARK_GRID_Y, DARK_TICK, chartTooltip } from '$lib/chart-setup';
	import { tightScale } from '$lib/chart-scale';

	let {
		score,
		change,
		events
	}: {
		score: DashboardOverview['score'];
		change: DashboardOverview['change'];
		events: DashboardOverview['events'];
	} = $props();

	type RangeKey = '7d' | '30d' | '90d' | '180d' | '360d';
	const RANGES = [
		{ key: '7d', days: 7 },
		{ key: '30d', days: 30 },
		{ key: '90d', days: 90 },
		{ key: '180d', days: 180 },
		{ key: '360d', days: 360 }
	] as const;
	let rangeKey = $state<RangeKey>('90d');

	const SCORE_COLOR = '#7ea8d8';
	const RAW_COLOR = 'rgba(255,255,255,0.14)';
	const EVENT_FILL = { low: 'rgba(232,93,74,0.06)', elevated: 'rgba(76,175,130,0.06)' };

	const rangeDays = $derived(RANGES.find((r) => r.key === rangeKey)?.days ?? 90);
	const timeUnit = $derived(rangeDays <= 31 ? 'day' : 'month');

	const windowed = $derived.by(() => score.slice(Math.max(0, score.length - rangeDays)));

	const yScale = $derived(tightScale(windowed.flatMap((p) => [p.raw, p.ma7])));

	const eventAnnotations = $derived.by(() => {
		if (!windowed.length) return {};
		const lo = windowed[0].date;
		const hi = windowed[windowed.length - 1].date;
		const out: Record<string, object> = {};
		for (const [i, ev] of events.entries()) {
			if (ev.end < lo || ev.start > hi) continue;
			out[`ev-${i}`] = {
				type: 'box',
				xMin: ev.start < lo ? lo : ev.start,
				xMax: ev.end > hi ? hi : ev.end,
				backgroundColor: EVENT_FILL[ev.kind] ?? 'rgba(255,255,255,0.022)',
				borderWidth: 0,
				label: {
					display: true,
					content: ev.label,
					position: { x: 'center', y: 'start' },
					color: '#6b8299',
					font: { size: 10 },
					backgroundColor: 'transparent'
				}
			};
		}
		return out;
	});

	const config = $derived.by<ChartConfiguration<'line'>>(() => ({
		type: 'line',
		data: {
			labels: windowed.map((p) => p.date),
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
					borderWidth: 2.25,
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
					time: { unit: timeUnit },
					grid: { display: false },
					border: DARK_BORDER,
					ticks: { color: DARK_TICK.color, maxRotation: 0, autoSkipPadding: 28 }
				},
				y: {
					min: yScale?.min,
					max: yScale?.max,
					afterBuildTicks: yScale
						? (axis) => {
								axis.ticks = yScale.ticks.map((value) => ({ value }));
							}
						: undefined,
					grid: DARK_GRID_Y,
					border: { display: false },
					ticks: { color: DARK_TICK.color }
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
							backgroundColor: 'rgba(126,168,216,0.08)',
							borderColor: 'rgba(126,168,216,0.16)',
							borderWidth: 1,
							label: {
								display: true,
								content: 'typical',
								position: { x: 'start', y: 'center' },
								color: '#6b8299',
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
						},
						...eventAnnotations
					}
				}
			}
		}
	}));

	const subtitle = $derived(
		change.is_meaningful && change.direction
			? `7-day average · ${change.direction} vs prior week (Δ ${change.delta7_z?.toFixed(1)} z)`
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
		<LineChart {config} height={320} />
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
		margin-bottom: 10px;
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
		padding: 3px 9px;
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
