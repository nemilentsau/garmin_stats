<script lang="ts" generics="TType extends keyof import('chart.js').ChartTypeRegistry">
	import { onMount } from 'svelte';
	import { Chart } from '$lib/chart-setup';
	import type { ChartConfiguration } from 'chart.js';

	let {
		config,
		type,
		height = 300,
		square = false
	}: {
		config: ChartConfiguration<TType>;
		type: TType;
		height?: number;
		square?: boolean;
	} = $props();

	let canvas: HTMLCanvasElement;
	let chart: Chart<TType> | null = null;

	onMount(() => {
		chart = new Chart(canvas, { ...config, type });
		return () => chart?.destroy();
	});

	$effect(() => {
		if (!chart) return;
		chart.data = config.data;
		if (config.options) {
			chart.options = config.options as Chart<TType>['options'];
		}
		chart.update();
	});

	const containerStyle = $derived(
		square
			? `height: ${height}px; max-width: ${height}px; margin: 0 auto; position: relative;`
			: `height: ${height}px; position: relative;`
	);
</script>

<div style={containerStyle}>
	<canvas bind:this={canvas}></canvas>
</div>
