<script lang="ts">
	import type { DashboardOverview } from '$lib/api';
	import { stateSentence, bandColor } from '$lib/recovery-format';
	import { parseIsoDate, fmtWeekdayDayMonth } from '$lib/date';
	import { fmtSigned } from '$lib/format';

	let { state, date }: { state: DashboardOverview['state']; date: string } = $props();

	const sentence = $derived(stateSentence(state));
	const color = $derived(bandColor(state.band));
	const dateLabel = $derived(fmtWeekdayDayMonth(parseIsoDate(date)));
	const zText = $derived(state.score_z == null ? '—' : `${fmtSigned(state.score_z)} z`);
</script>

<div class="state-line">
	<div class="left">
		<span class="dot" style="background:{color}"></span>
		<span class="sentence">{sentence}</span>
		<span class="score" style="color:{color}">{zText}</span>
	</div>
	<span class="date">{dateLabel}</span>
</div>

<style>
	.state-line {
		display: flex;
		align-items: baseline;
		justify-content: space-between;
		gap: 16px;
		padding-bottom: 14px;
		border-bottom: 1px solid rgba(255, 255, 255, 0.06);
	}
	.left {
		display: flex;
		align-items: baseline;
		gap: 10px;
		min-width: 0;
	}
	.dot {
		width: 9px;
		height: 9px;
		border-radius: 50%;
		align-self: center;
		flex-shrink: 0;
	}
	.sentence {
		font-size: 22px;
		font-weight: 600;
		letter-spacing: -0.01em;
		color: #e8f0f5;
	}
	.score {
		font-family: 'DM Mono', monospace;
		font-variant-numeric: tabular-nums lining-nums;
		font-size: 14px;
		opacity: 0.85;
	}
	.date {
		color: #5e7282;
		font-size: 12px;
		white-space: nowrap;
	}
	@media (max-width: 520px) {
		.sentence {
			font-size: 18px;
		}
	}
</style>
