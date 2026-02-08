<script lang="ts">
	let { title, children }: { title: string; children: () => any } = $props();
	let open = $state(false);
</script>

<div class="bg-blue-50 border border-blue-200 rounded-lg mb-6">
	<button
		class="w-full flex items-center justify-between px-4 py-3 text-left"
		onclick={() => (open = !open)}
	>
		<span class="text-sm font-medium text-blue-800">{title}</span>
		<svg
			class="w-4 h-4 text-blue-600 transition-transform {open ? 'rotate-180' : ''}"
			fill="none"
			stroke="currentColor"
			viewBox="0 0 24 24"
		>
			<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
		</svg>
	</button>
	{#if open}
		<div class="px-4 pb-3 text-sm text-blue-700 leading-relaxed">
			{@render children()}
		</div>
	{/if}
</div>
