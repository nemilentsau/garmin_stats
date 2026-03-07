<script lang="ts">
	import { onMount } from 'svelte';
	import { Chart } from '$lib/chart-setup';
	import type { ChartConfiguration } from 'chart.js';

	let { config, height = 300 }: { config: ChartConfiguration<'polarArea'>; height?: number } =
		$props();

	let canvas: HTMLCanvasElement;
	let chart: Chart<'polarArea'> | null = null;

	onMount(() => {
		chart = new Chart(canvas, { ...config, type: 'polarArea' });
		return () => {
			chart?.destroy();
		};
	});

	$effect(() => {
		if (!chart) return;
		chart.data = config.data;
		if (config.options) {
			chart.options = config.options as Chart<'polarArea'>['options'];
		}
		chart.update();
	});
</script>

<div style="height: {height}px; max-width: {height}px; margin: 0 auto; position: relative;">
	<canvas bind:this={canvas}></canvas>
</div>
