<script lang="ts">
	const WINDOWS = [30, 60, 90] as const;
	let { value, onchange }: { value: number; onchange: (w: number) => void } = $props();
</script>

<div class="range-picker">
	{#each WINDOWS as w}
		<button class="range-btn" class:active={value === w} onclick={() => onchange(w)}>{w}d</button>
	{/each}
</div>

<style>
	.range-picker {
		display: flex;
		gap: 4px;
	}
	.range-btn {
		padding: 3px 10px;
		font-size: 11px;
		font-family: 'DM Mono', monospace;
		font-weight: 400;
		color: #6b7d8e;
		background: transparent;
		border: 1px solid rgba(255,255,255,0.1);
		border-radius: 4px;
		cursor: pointer;
		transition: all 0.15s;
	}
	.range-btn:hover {
		color: #c8d6e0;
		border-color: rgba(255,255,255,0.2);
	}
	.range-btn.active {
		color: #c8d6e0;
		background: rgba(255,255,255,0.08);
		border-color: rgba(255,255,255,0.2);
	}
</style>
