<script lang="ts">
	let {
		title,
		value,
		unit = '',
		subtitle = '',
		colorClass = 'text-gray-900'
	}: {
		title: string;
		value: string | number;
		unit?: string;
		subtitle?: string;
		colorClass?: string;
	} = $props();
</script>

<div class="bg-white rounded-lg shadow p-4">
	<div class="text-xs font-medium text-gray-500 uppercase tracking-wide">{title}</div>
	<div class="mt-1 text-2xl font-bold {colorClass}">
		{value}
		{#if unit}<span class="text-sm font-normal text-gray-500">{unit}</span>{/if}
	</div>
	{#if subtitle}
		<div class="mt-0.5 text-xs text-gray-400">{subtitle}</div>
	{/if}
</div>
