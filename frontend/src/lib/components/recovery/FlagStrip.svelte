<script lang="ts">
	import type { DashboardOverview } from '$lib/api';
	import { flagDisplay, flagColor } from '$lib/recovery-format';
	import { parseIsoDate, fmtDayMonth } from '$lib/date';

	let {
		flags,
		flagSeries,
		hoveredDate = null
	}: {
		flags: DashboardOverview['flags'];
		flagSeries: DashboardOverview['flag_series'];
		hoveredDate?: string | null;
	} = $props();

	type HealthFlag = DashboardOverview['flags'][number];

	const seriesByKind = $derived(new Map(flagSeries.map((series) => [series.kind, series])));
	const displayFlags = $derived.by<HealthFlag[]>(() => {
		if (!hoveredDate) return flags;
		return flags.map((flag) => {
			const point = seriesByKind.get(flag.kind)?.points.find((p) => p.date === hoveredDate);
			if (!point) return flag;
			return {
				...flag,
				state: point.state,
				value: point.value,
				threshold_low: point.threshold_low,
				threshold_high: point.threshold_high,
				direction: point.direction,
				recent: point.recent
			};
		});
	});
	const whenLabel = $derived(hoveredDate ? fmtDayMonth(parseIsoDate(hoveredDate)) : 'today');
</script>

<section class="flag-strip">
	<span class="label">Health flags · {whenLabel}</span>
	<div class="chips">
		{#each displayFlags as flag (flag.kind)}
			{@const d = flagDisplay(flag)}
			{@const color = flagColor(d.tone)}
			<a class="chip" href={flag.tab_href} class:unknown={d.tone === 'unknown'}>
				<span class="dot" style="background:{color}"></span>
				<span class="text" style="color:{color}">{d.text}</span>
				{#if flag.recent && d.tone === 'clear'}<span class="recent">recent</span>{/if}
			</a>
		{/each}
	</div>
</section>

<style>
	.flag-strip {
		display: flex;
		align-items: center;
		gap: 16px;
		padding: 14px 0 4px;
		border-top: 1px solid rgba(255, 255, 255, 0.06);
		flex-wrap: wrap;
	}
	.label {
		font-size: 11px;
		color: #5e7282;
		text-transform: uppercase;
		letter-spacing: 0.04em;
	}
	.chips {
		display: flex;
		gap: 18px;
		flex-wrap: wrap;
	}
	.chip {
		display: inline-flex;
		align-items: center;
		gap: 7px;
		text-decoration: none;
		font-size: 13px;
	}
	.chip:hover .text {
		text-decoration: underline;
	}
	.dot {
		width: 8px;
		height: 8px;
		border-radius: 50%;
		flex-shrink: 0;
	}
	.chip.unknown .dot {
		background: repeating-linear-gradient(
			45deg,
			#5e7282,
			#5e7282 2px,
			transparent 2px,
			transparent 4px
		);
		border: 1px solid #5e7282;
	}
	.recent {
		font-size: 10px;
		color: #8a6a4a;
		text-transform: uppercase;
		letter-spacing: 0.03em;
	}
</style>
