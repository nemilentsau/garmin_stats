<script lang="ts">
	import type { DashboardOverview } from '$lib/api';
	import EvidenceSparkline from './EvidenceSparkline.svelte';
	import { recoveryColor, sourceGlyph, deltaArrow } from '$lib/recovery-format';
	import { fmt, fmtSigned } from '$lib/format';
	import { parseIsoDate, fmtDayMonth } from '$lib/date';

	let {
		evidence,
		driverSeries,
		dates,
		hoveredDate = null
	}: {
		evidence: DashboardOverview['evidence'];
		driverSeries: DashboardOverview['driver_series'];
		dates: string[];
		hoveredDate?: string | null;
	} = $props();

	type Row = DashboardOverview['evidence'][number];

	const driverByMetric = $derived(new Map(driverSeries.map((d) => [d.metric, d])));
	const hoverIndex = $derived(hoveredDate ? dates.indexOf(hoveredDate) : -1);
	// Count z-score inputs (not raw values) to match the backend's `degraded` rule:
	// a warm-up day can have a raw reading but no computable z yet.
	const presentAtHover = $derived(
		hoverIndex < 0 ? 7 : driverSeries.filter((d) => d.deltas_z[hoverIndex] != null).length
	);

	const absDelta = (z: number | null) => (z == null ? -1 : Math.abs(z));

	// Default: the latest-day rows (already metadata-rich). On hover: re-point each
	// row's value/baseline/Δz to the hovered day via the aligned driver series,
	// keeping label/unit/tab/sparkline. Re-sorted by impact either way.
	const displayRows = $derived.by<Row[]>(() => {
		const rows: Row[] =
			hoverIndex < 0
				? [...evidence]
				: evidence.map((meta) => {
						const ds = driverByMetric.get(meta.metric);
						const value = ds?.values[hoverIndex] ?? null;
						return {
							...meta,
							latest_value: value,
							baseline: ds?.baselines[hoverIndex] ?? null,
							delta_z: ds?.deltas_z[hoverIndex] ?? null,
							recovery_good: ds?.recovery_good[hoverIndex] ?? null,
							coverage_ok: value != null,
							degraded: presentAtHover < 7
						};
					});
		return rows.sort((a, b) => absDelta(b.delta_z) - absDelta(a.delta_z));
	});

	const whenLabel = $derived(hoveredDate ? fmtDayMonth(parseIsoDate(hoveredDate)) : 'today');

	function deltaText(z: number | null): string {
		return z == null ? '—' : fmtSigned(z);
	}
</script>

<section class="evidence">
	<header>
		<h2>What moved it</h2>
		<span class="hint" class:hovering={hoveredDate}>{whenLabel} vs your baseline · sorted by impact</span>
	</header>
	<table>
		<colgroup>
			<col style="width: 180px" />
			<col style="width: 96px" />
			<col style="width: 96px" />
			<col style="width: 80px" />
			<col />
		</colgroup>
		<thead>
			<tr>
				<th class="metric">metric</th>
				<th class="num">latest</th>
				<th class="num">baseline</th>
				<th class="num">Δz</th>
				<th class="spark">30 days</th>
			</tr>
		</thead>
		<tbody>
			{#each displayRows as row (row.metric)}
				{@const src = sourceGlyph(row.source_type)}
				{@const color = recoveryColor(row.recovery_good)}
				<tr>
					<td class="metric">
						<a href={row.tab_href} title={src.title}>{row.label}</a>
						{#if !row.coverage_ok}<span class="nodata" title="No reading today">no reading</span>{/if}
						{#if row.degraded}<span class="nodata" title="Score ran on fewer than 7 inputs">degraded</span>{/if}
					</td>
					<td class="num value">{fmt(row.latest_value)}{#if row.unit}<span class="unit">{row.unit}</span>{/if}</td>
					<td class="num baseline">{fmt(row.baseline)}</td>
					<td class="num delta" style="color:{color}">
						<span class="arrow">{deltaArrow(row.delta_z)}</span>{deltaText(row.delta_z)}
					</td>
					<td class="spark"><EvidenceSparkline points={row.sparkline} color="#5e7282" width={300} /></td>
				</tr>
			{/each}
		</tbody>
	</table>
</section>

<style>
	.evidence {
		padding: 18px 0;
		border-top: 1px solid rgba(255, 255, 255, 0.06);
	}
	header {
		display: flex;
		align-items: baseline;
		justify-content: space-between;
		gap: 12px;
		margin-bottom: 10px;
	}
	h2 {
		font-size: 13px;
		font-weight: 600;
		color: #c8d6e0;
		margin: 0;
		text-transform: uppercase;
		letter-spacing: 0.04em;
	}
	.hint {
		font-size: 12px;
		color: #5e7282;
		transition: color 0.12s;
	}
	.hint.hovering {
		color: #7ea8d8;
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
		padding: 4px 10px;
		text-align: right;
	}
	thead th.metric {
		text-align: left;
	}
	thead th.spark {
		text-align: center;
	}
	tbody td {
		padding: 7px 10px;
		border-top: 1px solid rgba(255, 255, 255, 0.04);
		vertical-align: middle;
	}
	.num {
		text-align: right;
		font-family: 'DM Mono', monospace;
		font-variant-numeric: tabular-nums lining-nums;
		white-space: nowrap;
	}
	.metric a {
		color: #e8f0f5;
		text-decoration: none;
		font-weight: 500;
	}
	.metric a:hover {
		color: #7ea8d8;
		text-decoration: underline;
	}
	.nodata {
		margin-left: 6px;
		font-size: 10px;
		color: #8a6a4a;
		text-transform: uppercase;
		letter-spacing: 0.03em;
	}
	.value {
		color: #e8f0f5;
	}
	.unit {
		color: #5e7282;
		font-size: 11px;
		margin-left: 2px;
	}
	.baseline {
		color: #8a9baa;
	}
	.delta .arrow {
		margin-right: 3px;
		font-size: 10px;
	}
	td.spark {
		text-align: center;
	}
	td.spark :global(svg) {
		margin: 0 auto;
	}
	@media (max-width: 640px) {
		th.spark,
		td.spark {
			display: none;
		}
	}
</style>
