<script lang="ts">
	/**
	 * RatingsGrid — shared rating-prompt inputs for card components.
	 *
	 * Renders one numeric input per prompt bound into the shared ratings map and
	 * snaps typed values to integers on commit (change/blur), so the emitted
	 * actual always satisfies the backend's dict[str, int] ratings contract.
	 * Used by StrengthSessionCard and MeditationTimerCard.
	 */
	import type { RatingPrompt } from './rating-helpers.js';

	let {
		prompts,
		ratings = $bindable(),
		onCommit
	}: {
		prompts: RatingPrompt[];
		ratings: Record<string, number | null>;
		onCommit?: () => void;
	} = $props();

	function commit(key: string) {
		const value = ratings[key];
		ratings[key] =
			typeof value === 'number' && Number.isFinite(value) ? Math.round(value) : null;
		onCommit?.();
	}
</script>

{#if prompts.length > 0}
	<div class="ratings-section">
		<div class="ratings-grid">
			{#each prompts as prompt}
				<label class="detail-field">
					<span class="field-label">{prompt.label}</span>
					<input
						type="number"
						bind:value={ratings[prompt.key]}
						min={prompt.scale_min}
						max={prompt.scale_max}
						step={1}
						placeholder="{prompt.scale_min}–{prompt.scale_max}"
						onchange={() => commit(prompt.key)}
						onblur={() => commit(prompt.key)}
					/>
				</label>
			{/each}
		</div>
	</div>
{/if}

<style>
	.ratings-section {
		margin-top: 4px;
	}

	.ratings-grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
		gap: 8px;
	}

	.detail-field {
		display: flex;
		flex-direction: column;
		gap: 6px;
	}

	.field-label {
		font-family: 'DM Mono', monospace;
		font-size: 10px;
		letter-spacing: 0.14em;
		text-transform: uppercase;
		color: #8fa3b0;
	}

	input[type='number'] {
		border: 1px solid rgba(255, 255, 255, 0.1);
		background: rgba(8, 15, 24, 0.7);
		color: #eef5f8;
		border-radius: 8px;
		padding: 8px 10px;
		font: inherit;
		font-size: 13px;
		width: 100%;
		box-sizing: border-box;
	}
</style>
