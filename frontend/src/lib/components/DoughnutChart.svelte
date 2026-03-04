<script lang="ts">
	import { onMount } from 'svelte';
	import { Chart } from '$lib/chart-setup';
	import type { ChartConfiguration } from 'chart.js';

	let { config, height = 300 }: { config: ChartConfiguration<'doughnut'>; height?: number } =
		$props();

	let canvas: HTMLCanvasElement;
	let chart: Chart<'doughnut'> | null = null;

	onMount(() => {
		chart = new Chart(canvas, { ...config, type: 'doughnut' });
		return () => {
			chart?.destroy();
		};
	});

	$effect(() => {
		if (!chart) return;
		chart.data = config.data;
		if (config.options) {
			chart.options = config.options as Chart<'doughnut'>['options'];
		}
		chart.update();
	});
</script>

<div style="height: {height}px; position: relative;">
	<canvas bind:this={canvas}></canvas>
</div>
