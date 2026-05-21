<script lang="ts">
	let {
		title,
		value,
		unit = '',
		subtitle = '',
		color = '#e8f0f5'
	}: {
		title: string;
		value: string | number;
		unit?: string;
		subtitle?: string;
		color?: string;
	} = $props();
</script>

<div class="bg-[rgba(255,255,255,0.02)] border border-[rgba(255,255,255,0.05)] rounded-lg p-4">
	<div class="text-xs font-medium text-[#8a9baa] uppercase tracking-wide">{title}</div>
	<div class="mt-1 text-2xl font-bold tabular-nums" style:color>
		{value}
		{#if unit}<span class="text-sm font-normal text-[#4a5c6a]">{unit}</span>{/if}
	</div>
	{#if subtitle}
		<div class="mt-0.5 text-xs text-[#5e7282]">{subtitle}</div>
	{/if}
</div>
