<script lang="ts">
	import type { Snippet } from 'svelte';
	import type { CardStatus } from '$lib/today-state';

	let {
		status,
		expanded,
		accent,
		icon = '',
		name,
		summary = null,
		brief = '',
		tags = [],
		backup = false,
		onToggleComplete,
		onSkip,
		onToggleDetails,
		children
	}: {
		status: CardStatus;
		expanded: boolean;
		accent: string;
		icon?: string;
		name: string;
		summary?: string | null;
		brief?: string;
		tags?: string[];
		backup?: boolean;
		onToggleComplete: () => void;
		onSkip: () => void;
		onToggleDetails: () => void;
		children: Snippet;
	} = $props();

	const isDone = $derived(status === 'completed');
	const isSkipped = $derived(status === 'skipped');
	const isPartial = $derived(status === 'partial');
</script>

<div
	class="activity-row"
	class:done={isDone}
	class:skipped={isSkipped}
	class:partial={isPartial}
	class:expanded
	style={`--dr-color: ${accent}`}
>
	<div class="row-main">
		<button
			type="button"
			class="check-toggle"
			class:checked={isDone}
			class:partial-check={isPartial}
			class:skipped-check={isSkipped}
			onclick={onToggleComplete}
			title={isDone ? 'Mark pending' : 'Mark done'}
		>
			{#if isDone}
				<svg viewBox="0 0 16 16" width="14" height="14" fill="none" aria-hidden="true">
					<path d="M3.5 8.5L6.5 11.5L12.5 4.5" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
				</svg>
			{:else if isSkipped}
				<svg viewBox="0 0 16 16" width="12" height="12" fill="none" aria-hidden="true">
					<path d="M4 4L12 12M12 4L4 12" stroke="currentColor" stroke-width="2" stroke-linecap="round" />
				</svg>
			{:else if isPartial}
				<svg viewBox="0 0 16 16" width="12" height="12" fill="none" aria-hidden="true">
					<path d="M3 8H13" stroke="currentColor" stroke-width="2" stroke-linecap="round" />
				</svg>
			{/if}
		</button>

		{#if icon}<span class="domain-icon">{icon}</span>{/if}

		<div class="row-content">
			<span class="row-name">{name}</span>
			{#if summary || backup}
				<span class="row-summary">
					{summary}{#if backup}<span class="backup-test"> · Backup test</span>{/if}
				</span>
			{/if}
		</div>

		{#if brief}<span class="row-brief">{brief}</span>{/if}
		{#if tags.length > 0}
			<div class="row-tags">
				{#each tags.slice(0, 2) as tag}<span class="mini-tag">{tag}</span>{/each}
			</div>
		{/if}

		<div class="row-actions">
			{#if !isDone}
				<button type="button" class="skip-btn" onclick={onSkip} title="Skip">
					<svg viewBox="0 0 16 16" width="14" height="14" fill="none" aria-hidden="true">
						<path d="M4 4L12 12M12 4L4 12" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" />
					</svg>
				</button>
			{/if}
			<button type="button" class="expand-btn" class:active={expanded} onclick={onToggleDetails} title="Details">
				<svg viewBox="0 0 16 16" width="14" height="14" fill="none" aria-hidden="true" style={`transform: rotate(${expanded ? 180 : 0}deg); transition: transform 0.2s`}>
					<path d="M4 6L8 10L12 6" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" />
				</svg>
			</button>
		</div>
	</div>

	{#if expanded}
		<div class="detail-panel">{@render children()}</div>
	{/if}
</div>

<style>
	.activity-row { border-radius: 10px; background: rgba(255,255,255,.025); border: 1px solid rgba(255,255,255,.05); border-left: 3px solid var(--dr-color,#5e7282); transition: background .15s, opacity .2s; }
	.activity-row:hover { background: rgba(255,255,255,.045); }
	.activity-row.done { opacity: .45; }
	.activity-row.done:hover { opacity: .7; }
	.activity-row.skipped { opacity: .35; }
	.activity-row.skipped:hover { opacity: .6; }
	.activity-row.partial { opacity: .6; }
	.activity-row.expanded { opacity: 1; background: rgba(255,255,255,.04); border-color: rgba(255,255,255,.1); border-left-color: var(--dr-color,#5e7282); }
	.row-main { display: flex; align-items: center; gap: 10px; padding: 10px 14px; min-height: 48px; }
	.check-toggle { flex-shrink: 0; width: 24px; height: 24px; border-radius: 6px; border: 2px solid rgba(255,255,255,.15); background: transparent; color: transparent; cursor: pointer; display: flex; align-items: center; justify-content: center; transition: border-color .15s, background .15s, color .15s; }
	.check-toggle:hover { border-color: rgba(91,181,166,.5); }
	.check-toggle.checked { background: rgba(91,181,166,.2); border-color: #5bb5a6; color: #7be0d0; }
	.check-toggle.partial-check { background: rgba(212,148,76,.15); border-color: #d4944c; color: #f3bf81; }
	.check-toggle.skipped-check { background: rgba(232,93,74,.12); border-color: rgba(232,93,74,.4); color: #f2a399; }
	.domain-icon { flex-shrink: 0; font-size: 14px; line-height: 1; opacity: .8; }
	.row-content { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 1px; }
	.row-name { font-family: 'Instrument Sans',sans-serif; font-size: 14px; font-weight: 600; color: #eef5f8; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
	.activity-row.done .row-name { text-decoration: line-through; text-decoration-color: rgba(91,181,166,.5); }
	.activity-row.skipped .row-name { text-decoration: line-through; text-decoration-color: rgba(232,93,74,.4); }
	.row-summary { font-size: 12px; color: #8fa3b0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
	.backup-test { color: #8fa3b0; }
	.row-brief { flex-shrink: 0; font-family: 'DM Mono',monospace; font-size: 11px; color: #6b8292; }
	.row-tags { display: flex; gap: 4px; flex-shrink: 0; }
	.mini-tag { padding: 2px 7px; border-radius: 4px; background: rgba(255,255,255,.05); font-family: 'DM Mono',monospace; font-size: 10px; color: #8fa3b0; }
	.row-actions { display: flex; align-items: center; gap: 4px; flex-shrink: 0; }
	.skip-btn,.expand-btn { width: 30px; height: 30px; border-radius: 6px; border: 1px solid rgba(255,255,255,.06); background: transparent; color: #6b8292; cursor: pointer; display: flex; align-items: center; justify-content: center; transition: background .15s,color .15s; }
	.skip-btn:hover { background: rgba(232,93,74,.1); color: #f2a399; }
	.expand-btn:hover,.expand-btn.active { background: rgba(255,255,255,.06); color: #c3d3dd; }
	.detail-panel { padding: 12px 14px 14px; border-top: 1px solid rgba(255,255,255,.06); display: flex; flex-direction: column; gap: 12px; }
	@media (max-width: 768px) { .row-main { flex-wrap: wrap; gap: 8px; } .row-tags,.row-brief { display: none; } }
</style>
