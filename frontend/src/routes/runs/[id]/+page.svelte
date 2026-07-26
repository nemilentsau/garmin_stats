<script lang="ts">
	import { page } from '$app/state';
	import { api, type CoachReview, type RunDetail, type RunSeries } from '$lib/api';
	import { errorMessage } from '$lib/utils';
	import { parseIsoDate, fmtWeekdayDayMonth } from '$lib/date';
	import { fmtSigned } from '$lib/format';
	import {
		fmtMiBare,
		fmtDuration,
		fmtPace,
		fmtPaceBare,
		fmtStartTime,
		hrBadgeLabel,
		fmtFt,
		fmtFtBare,
		fmtF,
		fmtMph,
		fmtCm,
		fmtCmBare
	} from '$lib/format-run';
	import { COLORS, withAlpha, DARK_MUTED_TEXT } from '$lib/colors';
	import { chartTooltip, DARK_GRID, DARK_GRID_Y, DARK_BORDER, DARK_TICK } from '$lib/chart-setup';
	import { tightScale } from '$lib/chart-scale';
	import { zoneColor } from '$lib/zone-colors';
	import LineChart from '$lib/components/LineChart.svelte';
	import ChartCanvas from '$lib/components/charts/ChartCanvas.svelte';
	import ChartCard from '$lib/components/ChartCard.svelte';
	import StatCard from '$lib/components/StatCard.svelte';
	import PageState from '$lib/components/PageState.svelte';
	import RunRouteMap from '$lib/components/RunRouteMap.svelte';
	import RunHeartRateEvidence from '$lib/components/RunHeartRateEvidence.svelte';
	import type { ChartConfiguration } from 'chart.js';

	// ── State ──
	// $state.raw, not deep $state: these are always replaced wholesale (never mutated
	// field-by-field), and their per-second arrays get handed straight to Chart.js —
	// which instruments array elements with its own property descriptors. A Svelte 5
	// deep-reactive proxy conflicts with that instrumentation (`state_descriptors_fixed`),
	// so the arrays must stay plain.
	let detail: RunDetail | null = $state.raw(null);
	let series: RunSeries | null = $state.raw(null);
	let loading = $state(true);
	let error: string | null = $state(null);
	let coachReview: CoachReview | null = $state(null);
	let coachReviewError: string | null = $state(null);
	let reviewBusy = $state(false);

	// Request token: run→run navigation re-fires the `$effect` below on every
	// `page.params.id` change; the token ensures a slow in-flight response for a
	// run the user has since navigated away from can never land and overwrite
	// the newer run's state (latest-wins), mirroring `todayRequestToken` in
	// today/+page.svelte.
	let runRequestToken = 0;

	async function loadCoachReview(id: string, requestToken: number) {
		coachReviewError = null;
		try {
			const review = await api.getCoachRunReview(id);
			if (requestToken !== runRequestToken) return;
			coachReview = review;
		} catch (e: unknown) {
			if (requestToken !== runRequestToken) return;
			coachReview = null;
			const message = errorMessage(e);
			if (!message.toLowerCase().includes('no coach review')) {
				coachReviewError = message;
			}
		}
	}

	async function requestCoachReview(id: string) {
		const requestToken = runRequestToken;
		reviewBusy = true;
		coachReviewError = null;
		try {
			const result = await api.enqueueCoachRunReview(id);
			if (requestToken !== runRequestToken) return;
			coachReview = result.review;
		} catch (e: unknown) {
			if (requestToken !== runRequestToken) return;
			coachReviewError = errorMessage(e);
		} finally {
			if (requestToken === runRequestToken) reviewBusy = false;
		}
	}

	async function loadRun(id: string, requestToken: number) {
		loading = true;
		try {
			const [nextDetail, nextSeries] = await Promise.all([api.getRun(id), api.getRunSeries(id)]);
			if (requestToken !== runRequestToken) return;
			detail = nextDetail;
			series = nextSeries;
			await loadCoachReview(id, requestToken);
			if (requestToken !== runRequestToken) return;
			error = null;
		} catch (e: unknown) {
			if (requestToken !== runRequestToken) return;
			detail = null;
			series = null;
			const message = errorMessage(e);
			// The backend 404s with a JSON `{"detail": "Run <id> not found"}` body; unwrap() stringifies
			// that into the Error message, so match on content rather than a status code we don't have.
			error = message.toLowerCase().includes('not found') ? 'Run not found.' : message;
		} finally {
			if (requestToken === runRequestToken) loading = false;
		}
	}

	// React to `page.params.id` changes (not just the initial mount) so run→run
	// navigation (e.g. from a "next run" link) loads the new run instead of
	// leaving the previous run's detail on screen. Per-run state is reset
	// synchronously before the fetch starts so nothing from the outgoing run
	// (coach review, its error) can flash over the incoming run's page.
	$effect(() => {
		const id = page.params.id;
		const requestToken = ++runRequestToken;
		detail = null;
		series = null;
		error = null;
		coachReview = null;
		coachReviewError = null;
		reviewBusy = false;
		if (id) void loadRun(id, requestToken);
	});

	// ── Pure display formatting (no computation/aggregation — every value below comes
	// straight from the backend response). fmtElapsed reuses the shared duration formatter
	// for chart-axis offsets, which happen to want the same h:mm:ss-drop-hour-under-1h shape. ──
	const fmtElapsed = fmtDuration;

	function fmtNum(v: number | null | undefined): string {
		return v == null ? '—' : Math.round(v).toLocaleString();
	}
	function fmtU0(v: number | null | undefined, unit: string): string {
		return v == null ? '—' : `${Math.round(v).toLocaleString()} ${unit}`;
	}
	function fmtU1(v: number | null | undefined, unit: string): string {
		return v == null ? '—' : `${v.toFixed(1)} ${unit}`;
	}
	function fmtMeters(v: number | null | undefined): string {
		return v == null ? '—' : `${v.toFixed(2)} m`;
	}
	function labelize(s: string | null | undefined): string {
		return s ? s.toLowerCase().replace(/_/g, ' ') : '';
	}
	function hasData(arr: (number | null)[] | undefined | null): boolean {
		return !!arr && arr.some((v) => v != null);
	}

	// ── Shared chart x-axis: elapsed seconds since session start, ticked as h:mm:ss/m:ss. ──
	let elapsedS = $derived.by(() => series?.chart.elapsed_s ?? []);

	let xScale = $derived.by(() => ({
		type: 'linear' as const,
		min: 0,
		max: elapsedS.length ? elapsedS[elapsedS.length - 1] : 0,
		ticks: { ...DARK_TICK, callback: (v: number | string) => fmtElapsed(Number(v)), maxTicksLimit: 12 },
		grid: DARK_GRID,
		border: DARK_BORDER
	}));

	// ── Per-channel line chart builder. Axes hug the data (tightScale); each channel supplies
	// its own value formatter/unit so ticks, tooltips, and footnotes never disagree. ──
	function channelConfig(
		label: string,
		data: (number | null)[],
		color: string,
		opts: {
			reverse?: boolean;
			area?: boolean;
			dots?: boolean;
			unit?: string;
			format?: (v: number) => string;
			/** Dashed reference line at y=0 (e.g. Performance Condition, which oscillates around a baseline). */
			zeroLine?: boolean;
		} = {}
	): ChartConfiguration<'line'> {
		const format = opts.format ?? ((v: number) => String(Math.round(v)));
		const values = data.filter((v): v is number => v !== null);
		const y = tightScale(values, 0.05);
		return {
			type: 'line',
			data: {
				labels: elapsedS,
				datasets: [
					{
						label,
						data,
						borderColor: color,
						backgroundColor: opts.area ? withAlpha(color, '22') : color,
						fill: opts.area ?? false,
						pointRadius: opts.dots ? 1.5 : 0,
						showLine: !opts.dots,
						borderWidth: 1.5,
						spanGaps: false
					}
				]
			},
			options: {
				responsive: true,
				maintainAspectRatio: false,
				animation: false,
				interaction: { mode: 'nearest', axis: 'x', intersect: false },
				plugins: {
					legend: { display: false },
					tooltip: {
						...chartTooltip(color),
						callbacks: {
							title: (items) => fmtElapsed(elapsedS[items[0]?.dataIndex ?? 0] ?? 0),
							label: (ctx) =>
								ctx.parsed.y == null
									? `${label}: —`
									: `${label}: ${format(ctx.parsed.y)}${opts.unit ? ' ' + opts.unit : ''}`
						}
					},
					...(opts.zeroLine
						? {
								annotation: {
									annotations: {
										zero: {
											type: 'line' as const,
											yMin: 0,
											yMax: 0,
											borderColor: '#4a5c6a',
											borderWidth: 1,
											borderDash: [4, 3]
										}
									}
								}
							}
						: {})
				},
				scales: {
					x: xScale,
					y: {
						min: y?.min,
						max: y?.max,
						reverse: opts.reverse ?? false,
						title: opts.unit ? { display: true, text: opts.unit, ...DARK_TICK } : undefined,
						ticks: { ...DARK_TICK, callback: (v: number | string) => format(Number(v)) },
						grid: DARK_GRID_Y,
						border: DARK_BORDER
					}
				}
			}
		};
	}

	// ── Stamina chart: two datasets (stamina + its ceiling, potential) sharing one fixed
	// 0-100 y-axis — a percentage-of-capacity gauge, the one deliberate exception to
	// tightScale (Garmin renders this range fixed too, not data-hugging). Bypasses
	// channelConfig since that builder only supports a single dataset. ──
	function staminaConfig(
		stamina: (number | null)[],
		potential: (number | null)[]
	): ChartConfiguration<'line'> {
		return {
			type: 'line',
			data: {
				labels: elapsedS,
				datasets: [
					{
						label: 'Stamina',
						data: stamina,
						borderColor: COLORS.stamina,
						backgroundColor: withAlpha(COLORS.stamina, '22'),
						fill: true,
						pointRadius: 0,
						borderWidth: 1.5,
						spanGaps: false
					},
					{
						label: 'Potential',
						data: potential,
						borderColor: COLORS.staminaPotential,
						backgroundColor: COLORS.staminaPotential,
						fill: false,
						pointRadius: 0,
						borderWidth: 1.5,
						borderDash: [4, 3],
						spanGaps: false
					}
				]
			},
			options: {
				responsive: true,
				maintainAspectRatio: false,
				animation: false,
				interaction: { mode: 'nearest', axis: 'x', intersect: false },
				plugins: {
					legend: {
						display: true,
						labels: { boxWidth: 12, font: { size: 11 }, color: DARK_MUTED_TEXT }
					},
					tooltip: {
						...chartTooltip(COLORS.stamina),
						callbacks: {
							title: (items) => fmtElapsed(elapsedS[items[0]?.dataIndex ?? 0] ?? 0),
							label: (ctx) =>
								ctx.parsed.y == null
									? `${ctx.dataset.label}: —`
									: `${ctx.dataset.label}: ${Math.round(ctx.parsed.y)}%`
						}
					}
				},
				scales: {
					x: xScale,
					y: {
						min: 0,
						max: 100,
						title: { display: true, text: '%', ...DARK_TICK },
						ticks: { ...DARK_TICK, callback: (v: number | string) => String(v) },
						grid: DARK_GRID_Y,
						border: DARK_BORDER
					}
				}
			}
		};
	}

	type ChartRow = { key: string; title: string; footnote: string; config: ChartConfiguration<'line'> };

	let chartRows = $derived.by<ChartRow[]>(() => {
		if (!series || !detail) return [];
		const s = series.series;
		const chart = series.chart;
		const session = detail.session;
		const d = detail.display;
		const rows: ChartRow[] = [];

		if (hasData(chart.altitude_ft)) {
			rows.push({
				key: 'elevation',
				title: 'Elevation',
				footnote: `smoothed · ↑ ${fmtFt(d.total_ascent_ft)} · ↓ ${fmtFt(d.total_descent_ft)}`,
				config: channelConfig('Elevation', chart.altitude_ft, COLORS.elevation, {
					area: true,
					unit: 'ft',
					format: (v) => String(Math.round(v))
				})
			});
		}

		if (hasData(chart.pace_min_per_mi)) {
			rows.push({
				key: 'pace',
				title: 'Pace',
				footnote: `avg ${fmtPace(d.pace_min_per_mi)}`,
				config: channelConfig('Pace', chart.pace_min_per_mi, COLORS.pace, {
					reverse: true,
					unit: '/mi',
					format: (v) => fmtPaceBare(v)
				})
			});
		}

		if (hasData(chart.cadence_spm)) {
			rows.push({
				key: 'cadence',
				title: 'Run Cadence',
				footnote: `avg ${fmtU0(session.avg_cadence_spm, 'spm')}`,
				config: channelConfig('Cadence', chart.cadence_spm, COLORS.cadence, {
					dots: true,
					unit: 'spm',
					format: (v) => String(Math.round(v))
				})
			});
		}

		if (hasData(chart.step_length_m)) {
			rows.push({
				key: 'stride',
				title: 'Stride Length',
				footnote: `avg ${fmtMeters(d.avg_step_length_m)}`,
				config: channelConfig('Stride Length', chart.step_length_m, COLORS.strideLength, {
					dots: true,
					unit: 'm',
					format: (v) => v.toFixed(2)
				})
			});
		}

		if (hasData(chart.power_w)) {
			rows.push({
				key: 'power',
				title: 'Power',
				footnote: `avg ${fmtNum(session.avg_power_w)} · max ${fmtNum(session.max_power_w)} · NP ${fmtNum(session.normalized_power_w)} W`,
				config: channelConfig('Power', chart.power_w, COLORS.power, {
					area: true,
					unit: 'W',
					format: (v) => String(Math.round(v))
				})
			});
		}

		if (hasData(chart.vertical_oscillation_cm)) {
			rows.push({
				key: 'vosc',
				title: 'Vertical Oscillation',
				footnote: `avg ${fmtCm(d.avg_vertical_oscillation_cm)}`,
				config: channelConfig('Vertical Oscillation', chart.vertical_oscillation_cm, COLORS.verticalOscillation, {
					dots: true,
					unit: 'cm',
					format: (v) => v.toFixed(1)
				})
			});
		}

		if (hasData(chart.vertical_ratio_pct)) {
			rows.push({
				key: 'vratio',
				title: 'Vertical Ratio',
				footnote: `avg ${fmtU1(session.avg_vertical_ratio_pct, '%')}`,
				config: channelConfig('Vertical Ratio', chart.vertical_ratio_pct, COLORS.verticalRatio, {
					dots: true,
					unit: '%',
					format: (v) => v.toFixed(1)
				})
			});
		}

		if (hasData(chart.ground_contact_time_ms)) {
			rows.push({
				key: 'gct',
				title: 'Ground Contact Time',
				footnote: `avg ${fmtU0(session.avg_ground_contact_time_ms, 'ms')}`,
				config: channelConfig('Ground Contact Time', chart.ground_contact_time_ms, COLORS.groundContactTime, {
					dots: true,
					unit: 'ms',
					format: (v) => String(Math.round(v))
				})
			});
		}

		if (hasData(chart.ground_contact_balance_pct)) {
			rows.push({
				key: 'gctBalance',
				title: 'GCT Balance',
				footnote: d.avg_ground_contact_balance_label ?? '—',
				config: channelConfig('GCT Balance', chart.ground_contact_balance_pct, COLORS.groundContactBalance, {
					dots: true,
					format: (v) => `${v.toFixed(1)}% L`
				})
			});
		}

		if (hasData(chart.respiration_rate_brpm)) {
			rows.push({
				key: 'respiration',
				title: 'Respiration Rate',
				footnote: `avg ${fmtU1(d.avg_respiration_rate_brpm, 'brpm')} · min ${fmtU1(d.min_respiration_rate_brpm, 'brpm')} · max ${fmtU1(d.max_respiration_rate_brpm, 'brpm')}`,
				config: channelConfig('Respiration Rate', chart.respiration_rate_brpm, COLORS.respiration, {
					area: true,
					unit: 'brpm',
					format: (v) => v.toFixed(1)
				})
			});
		}

		if (hasData(chart.temperature_f)) {
			rows.push({
				key: 'temp',
				title: 'Temperature',
				footnote: `min ${fmtF(d.min_temperature_f)} · avg ${fmtF(d.avg_temperature_f)} · max ${fmtF(d.max_temperature_f)}`,
				config: channelConfig('Temperature', chart.temperature_f, COLORS.temperature, {
					unit: '°F',
					format: (v) => v.toFixed(1)
				})
			});
		}

		if (hasData(chart.stamina_pct) || hasData(chart.stamina_potential_pct)) {
			rows.push({
				key: 'stamina',
				title: 'Stamina',
				footnote: `beginning ${fmtNum(d.stamina_beginning_potential_pct)}% · ending ${fmtNum(d.stamina_ending_potential_pct)}% · min ${fmtNum(d.stamina_min_pct)}%`,
				config: staminaConfig(chart.stamina_pct, chart.stamina_potential_pct)
			});
		}

		if (hasData(chart.performance_condition)) {
			rows.push({
				key: 'performanceCondition',
				title: 'Performance Condition',
				footnote: 'delta vs baseline fitness, ±10',
				config: channelConfig(
					'Performance Condition',
					chart.performance_condition,
					COLORS.performanceCondition,
					{ dots: true, zeroLine: true, format: (v) => String(Math.round(v)) }
				)
			});
		}

		return rows;
	});

	// ── Run/Walk band: horizontal floating-bar overview of the run's movement structure. ──
	type FloatingBarPoint = { x: [number, number]; y: string };
	const SPAN_ORDER = ['run', 'walk', 'stand'];
	const SPAN_COLORS: Record<string, string> = {
		run: COLORS.runSpan,
		walk: COLORS.walkSpan,
		stand: COLORS.standSpan
	};

	let runWalkConfig = $derived.by<ChartConfiguration<'bar', FloatingBarPoint[]> | null>(() => {
		if (!series) return null;
		const spans = series.series.run_walk_spans;
		if (!spans || spans.length === 0) return null;
		const categories = SPAN_ORDER.filter((t) => spans.some((sp) => sp.span_type === t));
		return {
			type: 'bar',
			data: {
				labels: categories,
				datasets: [
					{
						label: 'Run/Walk',
						data: spans.map((sp) => ({ x: [sp.start_s, sp.end_s] as [number, number], y: sp.span_type })),
						backgroundColor: spans.map((sp) => SPAN_COLORS[sp.span_type] ?? COLORS.baseline),
						borderWidth: 0,
						barThickness: 16
					}
				]
			},
			options: {
				indexAxis: 'y' as const,
				responsive: true,
				maintainAspectRatio: false,
				animation: false,
				plugins: {
					legend: { display: false },
					tooltip: {
						...chartTooltip(COLORS.baseline),
						callbacks: {
							label: (ctx) => {
								const sp = spans[ctx.dataIndex];
								return sp
									? `${sp.span_type}: ${fmtElapsed(sp.start_s)}–${fmtElapsed(sp.end_s)} (${fmtDuration(sp.end_s - sp.start_s)})`
									: '';
							}
						}
					}
				},
				scales: {
					x: xScale,
					y: { type: 'category' as const, labels: categories, ticks: { ...DARK_TICK }, grid: DARK_GRID_Y, border: DARK_BORDER }
				}
			}
		};
	});

	// ── Stats panel: definition-list groups (no cards). A group renders only when at least
	// one of its fields has a real value — e.g. no Power group on a run with no power meter. ──
	type StatRow = { label: string; value: string };
	type StatGroup = { title: string; rows: StatRow[] };

	let statGroups = $derived.by<StatGroup[]>(() => {
		if (!detail) return [];
		const s = detail.session;
		const d = detail.display;
		const groups: StatGroup[] = [];

		groups.push({
			title: 'Timing',
			rows: [
				{ label: 'Time', value: fmtDuration(s.timer_time_s) },
				{ label: 'Moving', value: fmtDuration(s.moving_time_s) },
				{ label: 'Elapsed', value: fmtDuration(s.elapsed_time_s) }
			]
		});

		groups.push({
			title: 'Pace / Speed',
			rows: [
				{ label: 'Avg Pace', value: fmtPace(d.pace_min_per_mi) },
				{ label: 'Avg Speed', value: fmtMph(d.avg_speed_mph) },
				{ label: 'Max Speed', value: fmtMph(d.max_speed_mph) },
				{ label: 'GAP', value: fmtPace(d.gap_min_per_mi) }
			]
		});

		if (s.avg_heart_rate_bpm != null) {
			const rows: StatRow[] = [
				{ label: 'Avg HR', value: fmtU0(s.avg_heart_rate_bpm, 'bpm') },
				{ label: 'Max HR', value: fmtU0(s.max_heart_rate_bpm, 'bpm') },
				{ label: 'Source', value: hrBadgeLabel(s.hr_source) ?? '—' }
			];
			if (s.hr_strap_battery != null) rows.push({ label: 'Strap Battery', value: s.hr_strap_battery });
			groups.push({ title: 'Heart Rate', rows });
		}

		if (s.avg_power_w != null) {
			groups.push({
				title: 'Power',
				rows: [
					{ label: 'Avg Power', value: fmtU0(s.avg_power_w, 'W') },
					{ label: 'Max Power', value: fmtU0(s.max_power_w, 'W') },
					{ label: 'Normalized Power', value: fmtU0(s.normalized_power_w, 'W') },
					{ label: 'Total Work', value: fmtU1(d.total_work_kj, 'kJ') }
				]
			});
		}

		if (
			s.avg_cadence_spm != null ||
			d.avg_step_length_m != null ||
			s.avg_vertical_oscillation_mm != null ||
			s.avg_ground_contact_time_ms != null
		) {
			groups.push({
				title: 'Running Dynamics',
				rows: [
					{ label: 'Avg Cadence', value: fmtU0(s.avg_cadence_spm, 'spm') },
					{ label: 'Max Cadence', value: fmtU0(s.max_cadence_spm, 'spm') },
					{ label: 'Stride Length', value: fmtMeters(d.avg_step_length_m) },
					{ label: 'Vert. Oscillation', value: fmtCm(d.avg_vertical_oscillation_cm) },
					{ label: 'Vert. Ratio', value: fmtU1(s.avg_vertical_ratio_pct, '%') },
					{ label: 'Ground Contact', value: fmtU0(s.avg_ground_contact_time_ms, 'ms') },
					{ label: 'GCT Balance', value: d.avg_ground_contact_balance_label ?? '—' },
					{ label: 'Stance Time', value: fmtU1(d.avg_stance_time_pct, '%') }
				]
			});
		}

		if (
			d.avg_respiration_rate_brpm != null ||
			d.min_respiration_rate_brpm != null ||
			d.max_respiration_rate_brpm != null
		) {
			groups.push({
				title: 'Respiration',
				rows: [
					{ label: 'Avg', value: fmtU1(d.avg_respiration_rate_brpm, 'brpm') },
					{ label: 'Min', value: fmtU1(d.min_respiration_rate_brpm, 'brpm') },
					{ label: 'Max', value: fmtU1(d.max_respiration_rate_brpm, 'brpm') }
				]
			});
		}

		if (
			d.stamina_beginning_potential_pct != null ||
			d.stamina_ending_potential_pct != null ||
			d.stamina_min_pct != null
		) {
			groups.push({
				title: 'Stamina',
				rows: [
					{ label: 'Beginning Potential', value: fmtU0(d.stamina_beginning_potential_pct, '%') },
					{ label: 'Ending Potential', value: fmtU0(d.stamina_ending_potential_pct, '%') },
					{ label: 'Min Stamina', value: fmtU0(d.stamina_min_pct, '%') }
				]
			});
		}

		if (s.total_ascent_m != null || s.total_descent_m != null) {
			groups.push({
				title: 'Elevation',
				rows: [
					{ label: 'Ascent', value: fmtFt(d.total_ascent_ft) },
					{ label: 'Descent', value: fmtFt(d.total_descent_ft) }
				]
			});
		}

		if (s.aerobic_training_effect != null || s.anaerobic_training_effect != null || s.training_load != null) {
			const label = labelize(s.training_effect_label);
			groups.push({
				title: 'Training Effect',
				rows: [
					{
						label: 'Aerobic',
						value: s.aerobic_training_effect != null
							? `${s.aerobic_training_effect.toFixed(1)}${label ? ' · ' + label : ''}`
							: '—'
					},
					{ label: 'Anaerobic', value: s.anaerobic_training_effect != null ? s.anaerobic_training_effect.toFixed(1) : '—' },
					{ label: 'Training Load', value: fmtNum(s.training_load) },
					{ label: 'VO2max', value: fmtU0(s.vo2max, 'ml/kg/min') },
					{ label: 'Body Battery Δ', value: s.body_battery_delta != null ? fmtSigned(s.body_battery_delta, 0) : '—' },
					{ label: 'Intensity Min.', value: d.intensity_minutes_label ?? '—' }
				]
			});
		}

		if (s.total_calories != null || s.steps != null || s.total_strides != null) {
			groups.push({
				title: 'Calories / Steps',
				rows: [
					{ label: 'Calories', value: fmtU0(s.total_calories, 'kcal') },
					{ label: 'Steps', value: fmtNum(s.steps) },
					{ label: 'Total Strides', value: fmtNum(s.total_strides) }
				]
			});
		}

		return groups;
	});

	// ── Laps table: only show columns that have at least one real value across laps. ──
	let lapColumns = $derived.by(() => {
		const laps = detail?.laps ?? [];
		const lapDisplays = detail?.display.lap_display ?? [];
		return {
			hr: laps.some((l) => l.avg_heart_rate_bpm != null),
			power: laps.some((l) => l.avg_power_w != null),
			cadence: laps.some((l) => l.avg_cadence_spm != null),
			gct: laps.some((l) => l.avg_ground_contact_time_ms != null),
			vertOsc: lapDisplays.some((l) => l.avg_vertical_oscillation_cm != null),
			balance: lapDisplays.some((l) => l.avg_ground_contact_balance_label != null),
			respiration: lapDisplays.some((l) => l.avg_respiration_rate_brpm != null)
		};
	});

	// Laps carry no unit-converted fields themselves; imperial distance/pace/vert-osc-cm and
	// the strap-dynamics display fields per lap come from `display.lap_display`, joined here
	// by `lap_index`.
	let lapDisplayByIndex = $derived.by(() => {
		const rows = detail?.display.lap_display ?? [];
		return new Map(rows.map((row) => [row.lap_index, row]));
	});

	// ── Power time-in-zone breakdown. Heart-rate zones live with the shared HR evidence. ──
	type ZoneRow = RunDetail['display']['heart_rate_zones'][number];

	let powerZoneRows = $derived.by<ZoneRow[]>(() => detail?.display.power_zones ?? []);
</script>

<svelte:head>
	<title>{detail ? (detail.session.activity_name ?? 'Run') : 'Run'} - Garmin Stats</title>
</svelte:head>

{#snippet zoneBar(rows: ZoneRow[])}
	<div class="zone-track">
		{#each rows as z (z.label)}
			<div
				class="zone-seg"
				style="flex-grow: {z.duration_s ?? 0}; background: {zoneColor(z.zone)};"
				title="{z.label}: {fmtDuration(z.duration_s)}"
			></div>
		{/each}
	</div>
	<div class="zone-legend">
		{#each rows as z (z.label)}
			<div class="zone-legend-row">
				<i class="zone-dot" style="background: {zoneColor(z.zone)};"></i>
				<span class="zone-label">{z.label}</span>
				<span class="zone-time">{fmtDuration(z.duration_s)}</span>
			</div>
		{/each}
	</div>
{/snippet}

<div class="run-detail-page">
	<PageState {error} {loading} loadingLabel="Loading run…">
		{#if detail && series}
			{@const session = detail.session}
			{@const display = detail.display}
			<div class="run-header">
				<a href="/runs" class="back-link">← Runs</a>
				<div class="run-header-main">
					<h1>{session.activity_name ?? 'Run'}</h1>
					<span class="run-header-date">
						{fmtWeekdayDayMonth(parseIsoDate(session.session_date))} · {fmtStartTime(session.start_time_local)}
						{#if session.location_name}· {session.location_name}{/if}
					</span>
				</div>
				{#if coachReview}
					<a class="coach-action" href={`/coach?review=${coachReview.id}`}>Open coach review</a>
				{:else}
					<button class="coach-action" onclick={() => requestCoachReview(session.id)} disabled={reviewBusy}>
						{reviewBusy ? 'Queueing…' : 'Review with coach'}
					</button>
				{/if}
			</div>
			{#if coachReviewError}
				<p class="coach-error">Coach review unavailable: {coachReviewError}</p>
			{/if}

			<div class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 mb-6">
				<StatCard title="Distance" value={fmtMiBare(display.distance_mi)} unit="mi" />
				<StatCard title="Time" value={fmtDuration(session.timer_time_s)} />
				<StatCard
					title="Avg Pace"
					value={fmtPaceBare(display.pace_min_per_mi)}
					unit="/mi"
					color={COLORS.pace}
				/>
				<StatCard
					title="Total Ascent"
					value={fmtFtBare(display.total_ascent_ft)}
					unit="ft"
					color={COLORS.elevation}
				/>
				<StatCard title="Calories" value={fmtNum(session.total_calories)} />
				{#if session.avg_heart_rate_bpm != null}
					<StatCard
						title="Avg HR"
						value={fmtNum(session.avg_heart_rate_bpm)}
						unit="bpm"
						subtitle={hrBadgeLabel(session.hr_source) ?? ''}
						color={COLORS.heartRate}
					/>
				{/if}
			</div>

			{#if session.has_gps_trace}
				<ChartCard title="Route">
					<div class="route-map-frame">
						<RunRouteMap lat={series.series.lat} lon={series.series.lon} pace={series.pace_min_per_mi} />
					</div>
				</ChartCard>
			{/if}

			{#if runWalkConfig}
				<!-- Chart.js bar types don't model [start, end] floating-bar tuples; cast to satisfy type-checker. -->
				<ChartCard title="Run / Walk">
					<ChartCanvas type="bar" config={runWalkConfig as unknown as ChartConfiguration<'bar'>} height={90} />
				</ChartCard>
			{/if}

			{#each chartRows as row (row.key)}
				<ChartCard title={row.title} footnote={row.footnote}>
					<LineChart config={row.config} height={200} />
				</ChartCard>
				{#if row.key === 'pace'}
					{#if series.heart_rate_evidence}
						<RunHeartRateEvidence
							elapsedS={series.chart.elapsed_s}
							heartRate={series.chart.heart_rate_bpm}
							evidence={series.heart_rate_evidence}
						/>
					{:else if hasData(series.series.heart_rate_bpm)}
						<p class="hr-evidence-unavailable">Heart-rate distribution evidence is unavailable for this run.</p>
					{/if}
				{/if}
			{/each}

			<section class="stats-panel">
				<h2 class="section-title">Session Stats</h2>
				<div class="stats-grid">
					{#each statGroups as group (group.title)}
						<div class="stat-group">
							<h3 class="stat-group-title">{group.title}</h3>
							<dl class="stat-rows">
								{#each group.rows as row (row.label)}
									<div class="stat-row">
										<dt>{row.label}</dt>
										<dd>{row.value}</dd>
									</div>
								{/each}
							</dl>
						</div>
					{/each}
				</div>
			</section>

			{#if detail.laps.length > 0}
				<section class="laps-section">
					<h2 class="section-title">Laps</h2>
					<table class="laps-table">
						<thead>
							<tr>
								<th class="left">#</th>
								<th class="num">distance (mi)</th>
								<th class="num">time</th>
								<th class="num">pace (/mi)</th>
								{#if lapColumns.hr}<th class="num">avg hr</th>{/if}
								{#if lapColumns.power}<th class="num">avg power</th>{/if}
								{#if lapColumns.cadence}<th class="num">cadence</th>{/if}
								{#if lapColumns.gct}<th class="num">gct</th>{/if}
								{#if lapColumns.balance}<th class="num">gct balance</th>{/if}
								{#if lapColumns.vertOsc}<th class="num">vert osc (cm)</th>{/if}
								{#if lapColumns.respiration}<th class="num">respiration</th>{/if}
							</tr>
						</thead>
						<tbody>
							{#each detail.laps as lap (lap.lap_index)}
								{@const lapDisplay = lapDisplayByIndex.get(lap.lap_index)}
								<tr>
									<td class="left">{lap.lap_index + 1}</td>
									<td class="num">{fmtMiBare(lapDisplay?.distance_mi ?? null)}</td>
									<td class="num">{fmtDuration(lap.timer_time_s)}</td>
									<td class="num">{fmtPaceBare(lapDisplay?.pace_min_per_mi ?? null)}</td>
									{#if lapColumns.hr}<td class="num">{fmtNum(lap.avg_heart_rate_bpm)}</td>{/if}
									{#if lapColumns.power}<td class="num">{fmtNum(lap.avg_power_w)}</td>{/if}
									{#if lapColumns.cadence}<td class="num">{fmtNum(lap.avg_cadence_spm)}</td>{/if}
									{#if lapColumns.gct}<td class="num">{fmtNum(lap.avg_ground_contact_time_ms)}</td>{/if}
									{#if lapColumns.balance}<td class="num">{lapDisplay?.avg_ground_contact_balance_label ?? '—'}</td>{/if}
									{#if lapColumns.vertOsc}<td class="num">{fmtCmBare(lapDisplay?.avg_vertical_oscillation_cm ?? null)}</td>{/if}
									{#if lapColumns.respiration}<td class="num">{fmtU1(lapDisplay?.avg_respiration_rate_brpm ?? null, 'brpm')}</td>{/if}
								</tr>
							{/each}
						</tbody>
					</table>
				</section>
			{/if}

			{#if powerZoneRows.length > 0}
				<section class="zones-section">
					<h2 class="section-title">Time in Zones</h2>
					<div class="zones-grid">
						{#if powerZoneRows.length > 0}
							<div class="zone-block">
								<h3 class="zone-block-title">Power Zones</h3>
								{@render zoneBar(powerZoneRows)}
							</div>
						{/if}
					</div>
				</section>
			{/if}
		{/if}
	</PageState>
</div>

<style>
	.run-detail-page {
		max-width: 1100px;
		margin: 0 auto;
		padding: 4px 0 24px;
	}

	.run-header {
		display: flex;
		align-items: baseline;
		gap: 16px;
		margin-bottom: 18px;
	}
	.back-link {
		font-family: 'DM Mono', monospace;
		font-size: 12px;
		letter-spacing: 0.03em;
		color: #6b7d8e;
		text-decoration: none;
		flex-shrink: 0;
	}
	.back-link:hover {
		color: #7ea8d8;
	}
	.run-header-main {
		display: flex;
		align-items: baseline;
		gap: 12px;
		flex-wrap: wrap;
	}
	.coach-action {
		margin-left: auto;
		flex-shrink: 0;
		border: 1px solid rgba(91, 181, 166, 0.28);
		background: rgba(91, 181, 166, 0.08);
		color: #7fc9bc;
		border-radius: 4px;
		padding: 7px 10px;
		font: 10px 'DM Mono', monospace;
		text-decoration: none;
		cursor: pointer;
	}
	.coach-action:disabled { opacity: 0.5; cursor: default; }
	.coach-error {
		margin: 6px 0 16px;
		color: #8a9baa;
		font-family: 'DM Mono', monospace;
		font-size: 11px;
	}
	.run-header-main h1 {
		margin: 0;
		font-size: 20px;
		font-weight: 700;
		color: #e8f0f5;
	}
	.run-header-date {
		font-family: 'DM Mono', monospace;
		font-size: 12px;
		color: #5e7282;
	}

	/* ── Route map: fixed-height frame so the Leaflet map has a concrete box to fill;
	     border-radius clips the tile layer to match the app's rounded card chrome. ── */
	.route-map-frame {
		height: 340px;
		border-radius: 6px;
		overflow: hidden;
	}
	.hr-evidence-unavailable {
		margin: 14px 0;
		padding: 14px 0;
		border-top: 1px solid rgba(255, 255, 255, 0.07);
		border-bottom: 1px solid rgba(255, 255, 255, 0.07);
		color: #6b7d8e;
		font: 11px 'DM Mono', monospace;
	}

	.section-title {
		font-size: 13px;
		font-weight: 600;
		color: #8a9baa;
		text-transform: uppercase;
		letter-spacing: 0.05em;
		margin: 28px 0 14px;
		padding-bottom: 8px;
		border-bottom: 1px solid rgba(255, 255, 255, 0.06);
	}

	/* ── Stats panel: aligned definition-list groups, deliberately NOT cards — a light
	     divider + heading groups each metric family without a card's enclosure/background. ── */
	.stats-grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
		gap: 20px 28px;
	}
	.stat-group {
		border-top: 1px solid rgba(255, 255, 255, 0.07);
		padding-top: 10px;
	}
	.stat-group-title {
		font-size: 11px;
		font-weight: 600;
		color: #6b7d8e;
		text-transform: uppercase;
		letter-spacing: 0.05em;
		margin: 0 0 8px;
	}
	.stat-rows {
		margin: 0;
	}
	.stat-row {
		display: flex;
		justify-content: space-between;
		align-items: baseline;
		gap: 12px;
		padding: 3px 0;
		font-size: 13px;
	}
	.stat-row dt {
		margin: 0;
		color: #8a9baa;
	}
	.stat-row dd {
		margin: 0;
		color: #e8f0f5;
		font-family: 'DM Mono', monospace;
		font-variant-numeric: tabular-nums lining-nums;
		text-align: right;
		white-space: nowrap;
	}

	/* ── Laps table (EvidenceTable styling) ── */
	.laps-table {
		width: 100%;
		border-collapse: collapse;
		font-size: 13px;
	}
	.laps-table thead th {
		font-weight: 500;
		font-size: 11px;
		color: #5e7282;
		text-transform: uppercase;
		letter-spacing: 0.03em;
		padding: 4px 10px 8px;
		text-align: right;
		border-bottom: 1px solid rgba(255, 255, 255, 0.06);
	}
	.laps-table thead th.left {
		text-align: left;
	}
	.laps-table tbody td {
		padding: 7px 10px;
		border-top: 1px solid rgba(255, 255, 255, 0.04);
		color: #c3d3dd;
	}
	.laps-table td.left {
		text-align: left;
		color: #e8f0f5;
		font-weight: 500;
	}
	.laps-table td.num {
		text-align: right;
		font-family: 'DM Mono', monospace;
		font-variant-numeric: tabular-nums lining-nums;
		white-space: nowrap;
		color: #e8f0f5;
	}

	/* ── Time in zones ── */
	.zones-grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
		gap: 24px;
	}
	.zone-block-title {
		font-size: 12px;
		font-weight: 600;
		color: #8a9baa;
		margin: 0 0 10px;
	}
	.zone-track {
		display: flex;
		height: 20px;
		border-radius: 4px;
		overflow: hidden;
		background: rgba(255, 255, 255, 0.03);
		margin-bottom: 10px;
	}
	.zone-seg {
		min-width: 0;
		transition: opacity 0.12s;
	}
	.zone-seg:hover {
		opacity: 0.8;
	}
	.zone-legend {
		display: flex;
		flex-direction: column;
		gap: 4px;
	}
	.zone-legend-row {
		display: flex;
		align-items: center;
		gap: 8px;
		font-size: 12px;
	}
	.zone-dot {
		width: 8px;
		height: 8px;
		border-radius: 2px;
		flex-shrink: 0;
	}
	.zone-label {
		color: #a8bac6;
		flex: 1;
	}
	.zone-time {
		font-family: 'DM Mono', monospace;
		font-variant-numeric: tabular-nums;
		color: #e8f0f5;
	}
</style>
