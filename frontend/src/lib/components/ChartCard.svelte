<script lang="ts">
	import type { Snippet } from 'svelte';

	let {
		title,
		footnote = '',
		compact = false,
		children
	}: {
		title: string;
		footnote?: string;
		compact?: boolean;
		children: Snippet;
	} = $props();
</script>

<div class="mb-6 rounded-lg border border-[rgba(255,255,255,0.05)] bg-[rgba(255,255,255,0.02)] p-5">
	<h2 class="mb-3 text-sm font-semibold uppercase tracking-wide text-[#8a9baa]">{title}</h2>
	{@render children()}
	{#if footnote}
		<p class="mt-2 text-xs text-[#4a5c6a]">{footnote}</p>
	{/if}
</div>
