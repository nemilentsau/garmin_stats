<script lang="ts">
	let { confidence }: { confidence: string } = $props();

	const styles: Record<string, { bg: string; text: string }> = {
		high: { bg: 'rgba(76, 175, 130, 0.15)', text: '#4CAF82' },
		moderate: { bg: 'rgba(91, 181, 166, 0.15)', text: '#5BB5A6' },
		low: { bg: 'rgba(212, 148, 76, 0.15)', text: '#D4944C' },
		insufficient: { bg: 'rgba(142, 158, 170, 0.15)', text: '#8e9eaa' }
	};

	const s = $derived(styles[confidence] ?? styles.insufficient);
</script>

<span
	class="inline-flex items-center rounded-full px-2.5 py-0.5 text-[11px] font-medium uppercase tracking-wider"
	style="background: {s.bg}; color: {s.text};"
>
	{confidence}
</span>
