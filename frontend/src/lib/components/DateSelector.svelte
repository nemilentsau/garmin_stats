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
	<label for="date-select" class="text-sm font-medium text-gray-700">View:</label>
	<select
		id="date-select"
		class="border border-gray-300 rounded-md px-3 py-1.5 text-sm bg-white focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
		value={selected}
		onchange={(e) => onchange(e.currentTarget.value)}
	>
		<option value="">All Days (Trend)</option>
		{#each days as day}
			<option value={day}>{day}</option>
		{/each}
	</select>
</div>
