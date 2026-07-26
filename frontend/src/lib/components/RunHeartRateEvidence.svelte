<script lang="ts">
	import type { ChartConfiguration } from 'chart.js';
	import type { RunSeries } from '$lib/api';
	import { COLORS, DARK_MUTED_TEXT, withAlpha } from '$lib/colors';
	import { chartTooltip, DARK_BORDER, DARK_GRID, DARK_GRID_Y, DARK_TICK } from '$lib/chart-setup';
	import { fmtDuration } from '$lib/format-run';
	import { zoneColor } from '$lib/zone-colors';
	import ChartCanvas from '$lib/components/charts/ChartCanvas.svelte';

	type Evidence = NonNullable<RunSeries['heart_rate_evidence']>;

	let {
		elapsedS,
		heartRate,
		evidence
	}: {
		elapsedS: number[];
		heartRate: (number | null)[];
		evidence: Evidence;
	} = $props();

	function fmtBpm(value: number): string {
		return `${Math.round(value)} bpm`;
	}

	let timelineConfig = $derived.by<ChartConfiguration<'line'>>(() => {
		const histogramMin = evidence.histogram[0]?.bpm;
		const histogramMax = evidence.histogram[evidence.histogram.length - 1]?.bpm;
		const annotations: Record<string, object> = {};
		for (const zone of evidence.zones) {
			const yMin = zone.lower_bound ?? histogramMin;
			const yMax = zone.upper_bound == null ? histogramMax : zone.upper_bound + 1;
			if (yMin == null || yMax == null || yMax <= yMin) continue;
			annotations[`zone-${zone.zone}`] = {
				type: 'box',
				yMin,
				yMax,
				backgroundColor: withAlpha(zoneColor(zone.zone), '12'),
				borderWidth: 0,
				label: {
					display: true,
					content: zone.label,
					position: 'end',
					xAdjust: -44,
					color: withAlpha(zoneColor(zone.zone), 'CC'),
					backgroundColor: 'transparent',
					font: { family: 'DM Mono', size: 9 }
				}
			};
		}
		return {
			type: 'line',
			data: {
				labels: elapsedS,
				datasets: [{
					label: 'Heart rate',
					data: heartRate,
					borderColor: COLORS.heartRate,
					backgroundColor: withAlpha(COLORS.heartRate, '18'),
					borderWidth: 1.5,
					pointRadius: 0,
					fill: true,
					spanGaps: false
				}]
			},
			options: {
				responsive: true,
				maintainAspectRatio: false,
				animation: false,
				interaction: { mode: 'nearest', axis: 'x', intersect: false },
				plugins: {
					legend: { display: false },
					tooltip: {
						...chartTooltip(COLORS.heartRate),
						callbacks: {
							title: (items) => fmtDuration(elapsedS[items[0]?.dataIndex ?? 0] ?? 0),
							label: (context) => context.parsed.y == null ? 'Heart rate: —' : `Heart rate: ${fmtBpm(context.parsed.y)}`
						}
					},
					annotation: { annotations }
				},
				scales: {
					x: {
						type: 'linear',
						ticks: { ...DARK_TICK, maxTicksLimit: 8, callback: (value) => fmtDuration(Number(value)) },
						grid: DARK_GRID,
						border: DARK_BORDER
					},
					y: {
						title: { display: true, text: 'bpm', ...DARK_TICK },
						ticks: DARK_TICK,
						grid: DARK_GRID_Y,
						border: DARK_BORDER
					}
				}
			}
		};
	});

	let histogramConfig = $derived.by<ChartConfiguration<'bar'>>(() => ({
		type: 'bar',
		data: {
			labels: evidence.histogram.map((bin) => bin.bpm),
			datasets: [{
				label: 'Recorded samples',
				data: evidence.histogram.map((bin) => bin.sample_pct),
				backgroundColor: evidence.histogram.map((bin) => {
					const zone = evidence.zones.find((row) =>
						(row.lower_bound == null || bin.bpm >= row.lower_bound) &&
						(row.upper_bound == null || bin.bpm <= row.upper_bound)
					);
					return withAlpha(zoneColor(zone?.zone ?? 1), 'A8');
				}),
				borderWidth: 0,
				barPercentage: 1,
				categoryPercentage: 1
			}]
		},
		options: {
			responsive: true,
			maintainAspectRatio: false,
			animation: false,
			plugins: {
				legend: { display: false },
				tooltip: {
					...chartTooltip(COLORS.heartRate),
					callbacks: {
						title: (items) => `${items[0]?.label ?? '—'} bpm`,
						label: (context) => {
							const bin = evidence.histogram[context.dataIndex];
							return bin ? `${bin.sample_count.toLocaleString()} samples · ${bin.sample_pct.toFixed(1)}%` : '—';
						}
					}
				}
			},
			scales: {
				x: {
					title: { display: true, text: 'bpm', ...DARK_TICK },
					ticks: { ...DARK_TICK, maxTicksLimit: 7 },
					grid: { display: false },
					border: DARK_BORDER
				},
				y: {
					beginAtZero: true,
					title: { display: true, text: 'samples (%)', ...DARK_TICK },
					ticks: { ...DARK_TICK, callback: (value) => `${value}%` },
					grid: DARK_GRID_Y,
					border: DARK_BORDER
				}
			}
		}
	}));
</script>

<section class="hr-evidence" aria-labelledby="hr-evidence-title">
	<header>
		<div>
			<h2 id="hr-evidence-title">Heart-rate evidence</h2>
			<p>Garmin zones · sample distribution, not duration</p>
		</div>
		<span>{evidence.present_samples.toLocaleString()} samples</span>
	</header>
	<div class="evidence-grid">
		<div>
			<h3>Trace within zone boundaries</h3>
			<ChartCanvas type="line" config={timelineConfig} height={240} />
		</div>
		<div>
			<h3>Where samples clustered</h3>
			<ChartCanvas type="bar" config={histogramConfig} height={240} />
		</div>
	</div>
	<dl>
		<div><dt>Q1</dt><dd>{fmtBpm(evidence.q1_bpm)}</dd></div>
		<div><dt>Median</dt><dd>{fmtBpm(evidence.median_bpm)}</dd></div>
		<div><dt>Q3</dt><dd>{fmtBpm(evidence.q3_bpm)}</dd></div>
		<div><dt>P90</dt><dd>{fmtBpm(evidence.p90_bpm)}</dd></div>
		<div><dt>Coverage</dt><dd>{evidence.coverage_pct.toFixed(1)}%</dd></div>
	</dl>
</section>

<style>
	.hr-evidence {
		margin: 16px 0;
		padding: 18px 0 14px;
		border-top: 1px solid rgba(255, 255, 255, 0.09);
		border-bottom: 1px solid rgba(255, 255, 255, 0.09);
	}
	header { display: flex; align-items: baseline; justify-content: space-between; gap: 16px; margin-bottom: 16px; }
	h2 { margin: 0; color: #dce7ed; font-size: 14px; font-weight: 650; }
	p, header > span, h3, dt { font-family: 'DM Mono', monospace; }
	p { margin: 4px 0 0; color: #657987; font-size: 10px; letter-spacing: .025em; }
	header > span { color: #718695; font-size: 10px; }
	.evidence-grid { display: grid; grid-template-columns: minmax(0, 1.8fr) minmax(260px, 1fr); gap: 28px; }
	h3 { margin: 0 0 8px; color: #8194a2; font-size: 10px; font-weight: 500; text-transform: uppercase; letter-spacing: .07em; }
	dl { display: flex; gap: 0; margin: 14px 0 0; padding-top: 12px; border-top: 1px solid rgba(255,255,255,.06); }
	dl > div { min-width: 104px; padding-right: 22px; }
	dt { color: #657987; font-size: 9px; text-transform: uppercase; letter-spacing: .08em; }
	dd { margin: 3px 0 0; color: #c9d6de; font: 12px 'DM Mono', monospace; font-variant-numeric: tabular-nums; }
	@media (max-width: 850px) { .evidence-grid { grid-template-columns: 1fr; } }
</style>
