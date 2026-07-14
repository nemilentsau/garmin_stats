<script lang="ts">
	import type { Snippet } from 'svelte';

	let {
		variantOptions,
		selectedVariant,
		note = $bindable(),
		onSelectVariant,
		onNoteBlur,
		children
	}: {
		variantOptions: string[];
		selectedVariant: string | null;
		note: string;
		onSelectVariant: (option: string) => void;
		onNoteBlur: () => void;
		children: Snippet;
	} = $props();
</script>

{#if variantOptions.length > 0}
	<div class="detail-field variant-field">
		<span>Variant</span>
		<div class="segment-row" role="group" aria-label="Variant taken">
			{#each variantOptions as option}
				<button type="button" class="seg-btn" class:selected={selectedVariant === option} aria-pressed={selectedVariant === option} onclick={() => onSelectVariant(option)}>
					{option}
				</button>
			{/each}
		</div>
	</div>
{/if}

{@render children()}

<label class="detail-field">
	<span>Notes</span>
	<textarea bind:value={note} rows="2" placeholder="Only record what matters." onblur={onNoteBlur}></textarea>
</label>

<style>
	.detail-field { display: flex; flex-direction: column; gap: 6px; }
	.detail-field span { font-family: 'DM Mono',monospace; font-size: 10px; letter-spacing: .14em; text-transform: uppercase; color: #8fa3b0; }
	textarea { border: 1px solid rgba(255,255,255,.1); background: rgba(8,15,24,.7); color: #eef5f8; border-radius: 8px; padding: 8px 10px; font: inherit; font-size: 13px; resize: vertical; }
	.segment-row { display: flex; gap: 0; border-radius: 8px; overflow: hidden; border: 1px solid rgba(91,181,166,.3); width: fit-content; }
	.seg-btn { padding: 6px 14px; border: none; border-right: 1px solid rgba(91,181,166,.2); background: rgba(91,181,166,.05); color: #8fa3b0; font: inherit; font-size: 12px; font-family: 'DM Mono',monospace; letter-spacing: .04em; cursor: pointer; transition: background .15s,color .15s; white-space: nowrap; }
	.seg-btn:last-child { border-right: none; }
	.seg-btn:hover:not(.selected) { background: rgba(91,181,166,.12); color: #c3d3dd; }
	.seg-btn.selected { background: rgba(91,181,166,.22); color: #7be0d0; }
</style>
