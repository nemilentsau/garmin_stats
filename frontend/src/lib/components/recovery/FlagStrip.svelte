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

	type OxygenHealthFlag = DashboardOverview['flags']['oxygen'];
	type ThermoregulationHealthFlag = DashboardOverview['flags']['thermoregulation'];
	type DisplayFlag = OxygenHealthFlag | ThermoregulationHealthFlag;

	const displayFlags = $derived.by<DisplayFlag[]>(() => {
		if (!hoveredDate) return [flags.oxygen, flags.thermoregulation];

		const oxygenPoint = flagSeries.oxygen.find((point) => point.date === hoveredDate);
		const thermoPoint = flagSeries.thermoregulation.find((point) => point.date === hoveredDate);
		const oxygen: OxygenHealthFlag = oxygenPoint
			? {
					...flags.oxygen,
					status: oxygenPoint.status,
					value: oxygenPoint.value,
					threshold_low: oxygenPoint.threshold_low
				}
			: flags.oxygen;
		const thermoregulation: ThermoregulationHealthFlag = thermoPoint
			? {
					...flags.thermoregulation,
					status: thermoPoint.status,
					value: thermoPoint.value,
					threshold_low: thermoPoint.threshold_low,
					threshold_high: thermoPoint.threshold_high
				}
			: flags.thermoregulation;

		return [oxygen, thermoregulation];
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
</style>
