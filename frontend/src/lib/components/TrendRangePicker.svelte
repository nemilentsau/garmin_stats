<script lang="ts">
	import { TREND_RANGES, type TrendRange } from '$lib/trend-range';

	let { value = $bindable<TrendRange>('3M') }: { value: TrendRange } = $props();
</script>

<div class="range-picker">
	{#each TREND_RANGES as r}
		<button
			class="range-btn"
			class:active={value === r}
			onclick={() => (value = r)}
		>{r}</button>
	{/each}
</div>

<style>
	.range-picker {
		display: flex;
		gap: 4px;
	}
	.range-btn {
		padding: 3px 10px;
		font-size: 11px;
		font-family: 'DM Mono', monospace;
		font-weight: 400;
		color: #6b7d8e;
		background: transparent;
		border: 1px solid rgba(255,255,255,0.1);
		border-radius: 4px;
		cursor: pointer;
		transition: all 0.15s;
	}
	.range-btn:hover {
		color: #c8d6e0;
		border-color: rgba(255,255,255,0.2);
	}
	.range-btn.active {
		color: #c8d6e0;
		background: rgba(255,255,255,0.08);
		border-color: rgba(255,255,255,0.2);
	}
</style>
