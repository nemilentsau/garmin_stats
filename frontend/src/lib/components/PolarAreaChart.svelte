<script lang="ts">
	import type { ChartConfiguration } from 'chart.js';
	import ChartCanvas from '$lib/components/charts/ChartCanvas.svelte';

	let { config, height = 300 }: { config: ChartConfiguration<'polarArea'>; height?: number } =
		$props();
</script>

<ChartCanvas type="polarArea" {config} {height} square />
