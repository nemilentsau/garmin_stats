<script lang="ts" generics="T extends string | number">
	// Presentational segmented toggle (a row of mutually-exclusive pills). Owns the shared
	// `.range-picker`/`.range-btn` look so the concrete pickers (TrendRangePicker,
	// BaselineWindowPicker) stay one-liner wrappers and can't drift out of visual sync.
	let {
		options,
		value,
		onchange,
		disabled = false,
		label = (v: T) => String(v)
	}: {
		options: readonly T[];
		value: T;
		onchange: (v: T) => void;
		disabled?: boolean;
		/** Render text for an option (defaults to its string form). */
		label?: (v: T) => string;
	} = $props();
</script>

<div class="range-picker">
	{#each options as opt}
		<button
			class="range-btn"
			class:active={value === opt}
			{disabled}
			onclick={() => onchange(opt)}>{label(opt)}</button
		>
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
	.range-btn:disabled {
		opacity: 0.4;
		cursor: default;
	}
	.range-btn:disabled:hover {
		color: #6b7d8e;
		border-color: rgba(255,255,255,0.1);
	}
</style>
