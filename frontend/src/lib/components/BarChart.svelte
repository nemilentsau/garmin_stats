<script lang="ts">
	import { onMount } from 'svelte';
	import { Chart } from '$lib/chart-setup';
	import type { ChartConfiguration } from 'chart.js';

	let { config, height = 300 }: { config: ChartConfiguration<'bar'>; height?: number } = $props();

	let canvas: HTMLCanvasElement;
	let chart: Chart<'bar'> | null = null;

	onMount(() => {
		chart = new Chart(canvas, { ...config, type: 'bar' });
		return () => {
			chart?.destroy();
		};
	});

	$effect(() => {
		if (!chart) return;
		chart.data = config.data;
		if (config.options) {
			chart.options = config.options as Chart<'bar'>['options'];
		}
		chart.update();
	});
</script>

<div style="height: {height}px; position: relative;">
	<canvas bind:this={canvas}></canvas>
</div>
