<script lang="ts">
	import TrendRangePicker from '$lib/components/TrendRangePicker.svelte';
	import type { TrendRange } from '$lib/trend-range';

	let {
		title,
		trendRange = $bindable(),
		showTrendRange = true
	}: {
		title: string;
		trendRange?: TrendRange;
		showTrendRange?: boolean;
	} = $props();
</script>

<div class="mb-4 flex items-center justify-between gap-4">
	<h1 class="text-xl font-bold text-[#e8f0f5]">{title}</h1>
	{#if showTrendRange && trendRange}
		<TrendRangePicker bind:value={trendRange} />
	{/if}
</div>
