<script lang="ts">
	import type { ChartConfiguration } from 'chart.js';
	import ChartCanvas from '$lib/components/charts/ChartCanvas.svelte';

	let { config, height = 300 }: { config: ChartConfiguration<'scatter'>; height?: number } =
		$props();
</script>

<ChartCanvas type="scatter" {config} {height} />
