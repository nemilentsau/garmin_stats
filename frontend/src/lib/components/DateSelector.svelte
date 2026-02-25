<script lang="ts">
	let {
		days,
		selected = '',
		onchange
	}: {
		days: string[];
		selected?: string;
		onchange: (date: string) => void;
	} = $props();
</script>

<div class="flex items-center gap-2 mb-6">
	<label for="date-select" class="text-sm font-medium text-[#8a9baa]">View:</label>
	<select
		id="date-select"
		class="border border-[rgba(255,255,255,0.1)] rounded-md px-3 py-1.5 text-sm bg-[rgba(255,255,255,0.05)] text-[#c8d6e0] focus:ring-2 focus:ring-[rgba(91,181,166,0.4)] focus:border-[rgba(91,181,166,0.4)]"
		value={selected}
		onchange={(e) => onchange(e.currentTarget.value)}
	>
		<option value="">All Days (Trend)</option>
		{#each days as day}
			<option value={day}>{day}</option>
		{/each}
	</select>
</div>
