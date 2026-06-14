<script lang="ts">
	import type { DashboardOverview } from '$lib/api';
	import { flagDisplay, flagColor, healthFlagStripViewModel } from '$lib/recovery-format';

	let {
		flags,
		flagSeries,
		latestDate,
		hoveredDate = null
	}: {
		flags: DashboardOverview['flags'];
		flagSeries: DashboardOverview['flag_series'];
		latestDate: string;
		hoveredDate?: string | null;
	} = $props();

	const viewModel = $derived(
		healthFlagStripViewModel({ flags, flagSeries, latestDate, hoveredDate })
	);
</script>

<section class="flag-strip">
	<span class="label">Health flags · {viewModel.whenLabel}</span>
	<div class="chips">
		{#each viewModel.flags as flag (flag.kind)}
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
