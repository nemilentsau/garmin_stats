<script lang="ts">
	import type { Snippet } from 'svelte';

	let {
		error,
		loading,
		loadingLabel = 'Loading...',
		children
	}: {
		error: string | null;
		loading: boolean;
		loadingLabel?: string;
		children: Snippet;
	} = $props();
</script>

{#if error}
	<div class="rounded-lg border border-[rgba(232,93,74,0.3)] bg-[rgba(232,93,74,0.08)] p-4">
		<p class="text-[#E85D4A]">Error: {error}</p>
	</div>
{:else if loading}
	<div class="flex h-64 items-center justify-center">
		<div class="text-[#5e7282]">{loadingLabel}</div>
	</div>
{:else}
	{@render children()}
{/if}
