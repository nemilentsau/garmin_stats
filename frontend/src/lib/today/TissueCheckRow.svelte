<script lang="ts">
	const SCALE_LEVELS = [0, 1, 2, 3] as const;
	type ScaleLevel = (typeof SCALE_LEVELS)[number];

	let {
		label,
		detail = null,
		mode,
		scale,
		flagged,
		onSelectScale,
		onToggleFlag
	}: {
		label: string;
		detail?: string | null;
		mode: 'log' | 'view';
		scale: number | null;
		flagged: boolean;
		onSelectScale?: (level: ScaleLevel) => void;
		onToggleFlag?: () => void;
	} = $props();
</script>

{#if mode === 'view'}
	<div class="detail-row">
		<div class="label-wrap">
			<strong>{label}</strong>
			{#if detail}<small>{detail}</small>{/if}
		</div>
		{#if scale !== null}
			<span class="tissue-summary">{scale}{#if flagged}&nbsp;⚑{/if}</span>
		{:else}
			<span class="tissue-summary unanswered">–</span>
		{/if}
	</div>
{:else}
	<div class="tissue-row">
		<div class="label-wrap">
			<strong>{label}</strong>
			{#if detail}<small>{detail}</small>{/if}
		</div>
		<div class="tissue-controls">
			<div class="scale-chips" role="group" aria-label={`${label} soreness level`}>
				{#each SCALE_LEVELS as level}
					<button
						type="button"
						class="chip"
						class:selected={scale === level}
						aria-pressed={scale === level}
						onclick={() => onSelectScale?.(level)}
					>
						{level}
					</button>
				{/each}
			</div>
			<button
				type="button"
				class="flag-btn"
				class:flagged
				aria-pressed={flagged}
				title="pain above background noise"
				onclick={() => onToggleFlag?.()}
			>
				<svg viewBox="0 0 16 16" width="12" height="12" fill="none" aria-hidden="true">
					<path d="M4 1.5v13" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" />
					<path
						d="M4 2.2c1.5-0.9 3-0.9 4.5 0s3 0.9 4.5 0v6.2c-1.5 0.9-3 0.9-4.5 0s-3-0.9-4.5 0V2.2z"
						stroke="currentColor"
						stroke-width="1.2"
						stroke-linejoin="round"
						stroke-linecap="round"
					/>
				</svg>
			</button>
		</div>
	</div>
{/if}

<style>
	.detail-row,
	.tissue-row {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 10px;
		padding: 8px 10px;
		border-radius: 8px;
		background: rgba(255, 255, 255, 0.03);
		font-size: 13px;
	}

	.label-wrap {
		min-width: 0;
	}

	.label-wrap strong {
		display: block;
		font-size: 13px;
	}

	.label-wrap small {
		display: block;
		margin-top: 2px;
		color: #6b8292;
		font-size: 11px;
	}

	.tissue-summary {
		flex-shrink: 0;
		font-family: 'DM Mono', monospace;
		font-size: 12px;
		font-variant-numeric: tabular-nums;
		color: #c3d3dd;
		white-space: nowrap;
	}

	.tissue-summary.unanswered {
		color: #4a5568;
	}

	.tissue-controls {
		display: flex;
		align-items: center;
		gap: 8px;
		flex-shrink: 0;
	}

	.scale-chips {
		display: flex;
		gap: 0;
		border-radius: 7px;
		overflow: hidden;
		border: 1px solid rgba(74, 144, 217, 0.25);
	}

	.chip {
		width: 26px;
		height: 26px;
		border: none;
		border-right: 1px solid rgba(74, 144, 217, 0.2);
		background: rgba(74, 144, 217, 0.05);
		color: #6b8292;
		font: inherit;
		font-size: 12px;
		font-family: 'DM Mono', monospace;
		font-variant-numeric: tabular-nums;
		cursor: pointer;
		transition:
			background 0.15s,
			color 0.15s;
	}

	.chip:last-child {
		border-right: none;
	}

	.chip:hover:not(.selected) {
		background: rgba(74, 144, 217, 0.12);
		color: #a7bac6;
	}

	.chip.selected {
		background: rgba(74, 144, 217, 0.22);
		color: #4a90d9;
	}

	.flag-btn {
		flex-shrink: 0;
		width: 26px;
		height: 26px;
		border-radius: 7px;
		border: 1px solid rgba(255, 255, 255, 0.1);
		background: transparent;
		color: #4a5568;
		cursor: pointer;
		display: flex;
		align-items: center;
		justify-content: center;
		transition:
			background 0.15s,
			color 0.15s,
			border-color 0.15s;
	}

	.flag-btn:hover {
		color: #f2a399;
		border-color: rgba(232, 93, 74, 0.3);
	}

	.flag-btn.flagged {
		background: rgba(232, 93, 74, 0.15);
		border-color: rgba(232, 93, 74, 0.4);
		color: #f2a399;
	}
</style>
