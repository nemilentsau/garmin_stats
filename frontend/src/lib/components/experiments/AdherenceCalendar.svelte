<script lang="ts">
	import type { AdherenceDayEntry } from '$lib/api';

	let { entries, rate }: { entries: AdherenceDayEntry[]; rate: number } = $props();

	function stateColor(state: string): string {
		if (state === 'full' || state === 'completed') return '#4CAF82';
		if (state === 'partial') return '#D4944C';
		if (state === 'missed') return '#E85D4A';
		return 'rgba(255,255,255,0.06)';
	}

	function stateLabel(state: string): string {
		if (state === 'full' || state === 'completed') return 'Done';
		if (state === 'partial') return 'Partial';
		if (state === 'missed') return 'Missed';
		return 'Unknown';
	}

	function dayLabel(dateStr: string): string {
		const d = new Date(dateStr + 'T12:00:00');
		return d.getDate().toString();
	}
</script>

<div class="rounded-xl border border-[rgba(255,255,255,0.05)] bg-[rgba(255,255,255,0.02)] p-5">
	<div class="mb-3 flex items-center justify-between">
		<h3 class="font-['DM_Mono',monospace] text-sm text-[#8a9baa]">Adherence</h3>
		<span class="text-lg font-bold" class:text-[#4CAF82]={rate >= 0.7} class:text-[#D4944C]={rate < 0.7 && rate >= 0.5} class:text-[#E85D4A]={rate < 0.5}>
			{(rate * 100).toFixed(0)}%
		</span>
	</div>

	<div class="flex flex-wrap gap-1">
		{#each entries as entry}
			<div
				class="flex h-6 w-6 items-center justify-center rounded text-[9px] font-medium text-[#0d1520]"
				style="background: {stateColor(entry.state)};"
				title="{entry.date}: {stateLabel(entry.state)}"
			>
				{dayLabel(entry.date)}
			</div>
		{/each}
	</div>

	<div class="mt-3 flex gap-4 text-[10px] text-[#5e7282]">
		<span><span class="inline-block h-2 w-2 rounded-sm" style="background:#4CAF82"></span> Done</span>
		<span><span class="inline-block h-2 w-2 rounded-sm" style="background:#D4944C"></span> Partial</span>
		<span><span class="inline-block h-2 w-2 rounded-sm" style="background:#E85D4A"></span> Missed</span>
		<span><span class="inline-block h-2 w-2 rounded-sm" style="background:rgba(255,255,255,0.06)"></span> Unknown</span>
	</div>
</div>
