<script lang="ts">
	/**
	 * ChecklistCard — renders a checklist payload in view or log mode.
	 *
	 * Items come in two kinds (ChecklistItem.kind): `checkbox` items are answered with
	 * checked/text (a done/not-done item with an optional note); `tissue_check` items are
	 * answered with scale/flagged (a 0-3 soreness rating plus a "pain above background
	 * noise" flag, used for the per-tissue morning check-in). Each item's kind is fixed by
	 * the template, not user-chosen.
	 *
	 * view mode: static list of items + optional instructions; tissue_check items render
	 * their logged scale/flag compactly, or a muted "–" when unanswered.
	 * log mode: checkbox-or-scale-chips per item with optional free-text answer (checkbox
	 * items only); emits ChecklistActual on every change so the parent (Today board) can
	 * stash + debounce-persist it.
	 *
	 * The component is always freshly mounted when a card's detail panel opens ({#if isExpanded}),
	 * so reading card.actual_json once at construction via untrack is correct and sufficient.
	 * A reactive $effect would re-seed checkedMap/textMap/scaleMap/flaggedMap on every
	 * debounced persist, wiping in-progress user input that hasn't been saved yet.
	 */
	import { untrack } from 'svelte';
	import type { ScheduleOccurrence, TodayCard } from '$lib/api';

	type ChecklistPayload = Extract<ScheduleOccurrence['payload_json'], { card_type: 'checklist' }>;
	type FullActual = TodayCard['actual_json'];
	export type ChecklistActual = {
		card_type: 'checklist';
		answers: {
			item_id: string;
			checked: boolean;
			text: string | null;
			scale: number | null;
			flagged: boolean;
		}[];
	};

	let {
		card,
		mode,
		onActual
	}: {
		card: { payload_json: ChecklistPayload; actual_json?: FullActual };
		mode: 'log' | 'view';
		onActual?: (actual: ChecklistActual) => void;
	} = $props();

	const items = $derived(card.payload_json.items ?? []);

	// ── One-time synchronous init — never re-runs when actual_json changes ────
	const initialActual = untrack(() =>
		card.actual_json?.card_type === 'checklist' ? card.actual_json : null
	);
	const initialItems = untrack(() => card.payload_json.items ?? []);

	let checkedMap = $state<Record<string, boolean>>(
		Object.fromEntries(
			initialItems.map((item) => {
				const answer = initialActual?.answers.find((a: { item_id: string }) => a.item_id === item.id);
				return [item.id, answer?.checked ?? false];
			})
		)
	);
	let textMap = $state<Record<string, string>>(
		Object.fromEntries(
			initialItems.map((item) => {
				const answer = initialActual?.answers.find((a: { item_id: string }) => a.item_id === item.id);
				return [item.id, answer?.text ?? ''];
			})
		)
	);
	// tissue_check state — scale defaults to 0 (visually "no soreness") when no answer was
	// ever stored, mirroring checkedMap's default-false: the default is a real, persistable
	// value, not a null placeholder, so it round-trips through emit() like any other answer.
	let scaleMap = $state<Record<string, number>>(
		Object.fromEntries(
			initialItems.map((item) => {
				const answer = initialActual?.answers.find((a: { item_id: string }) => a.item_id === item.id);
				return [item.id, answer?.scale ?? 0];
			})
		)
	);
	let flaggedMap = $state<Record<string, boolean>>(
		Object.fromEntries(
			initialItems.map((item) => {
				const answer = initialActual?.answers.find((a: { item_id: string }) => a.item_id === item.id);
				return [item.id, answer?.flagged ?? false];
			})
		)
	);

	const SCALE_LEVELS = [0, 1, 2, 3] as const;

	function emit() {
		onActual?.({
			card_type: 'checklist',
			answers: items.map((item) => {
				if (item.kind === 'tissue_check') {
					return {
						item_id: item.id,
						checked: false,
						text: null,
						scale: scaleMap[item.id] ?? 0,
						flagged: flaggedMap[item.id] ?? false
					};
				}
				return {
					item_id: item.id,
					checked: checkedMap[item.id] ?? false,
					text: textMap[item.id]?.trim() || null,
					scale: null,
					flagged: false
				};
			})
		});
	}

	function selectScale(itemId: string, level: (typeof SCALE_LEVELS)[number]) {
		scaleMap[itemId] = level;
		emit();
	}

	function toggleFlag(itemId: string) {
		flaggedMap[itemId] = !flaggedMap[itemId];
		emit();
	}
</script>

{#if card.payload_json.instructions}
	<p class="detail-copy">{card.payload_json.instructions}</p>
{/if}

{#if mode === 'view'}
	{#if items.length > 0}
		<div class="detail-list">
			{#each items as item}
				{#if item.kind === 'tissue_check'}
					{@const answer = initialActual?.answers.find(
						(a: { item_id: string }) => a.item_id === item.id
					)}
					<div class="detail-row tissue-view-row">
						<div class="detail-row-content">
							<strong>{item.label}</strong>
							{#if item.detail}
								<small>{item.detail}</small>
							{/if}
						</div>
						{#if answer}
							<span class="tissue-summary">
								{answer.scale ?? 0}{#if answer.flagged}&nbsp;⚑{/if}
							</span>
						{:else}
							<span class="tissue-summary unanswered">–</span>
						{/if}
					</div>
				{:else}
					<div class="detail-row">
						<div class="detail-row-content">
							<strong>{item.label}</strong>
							{#if item.detail}
								<small>{item.detail}</small>
							{/if}
						</div>
					</div>
				{/if}
			{/each}
		</div>
	{/if}
{:else}
	{#if items.length > 0}
		<div class="checklist">
			{#each items as item}
				{#if item.kind === 'tissue_check'}
					<div class="tissue-row">
						<div class="tissue-label-wrap">
							<strong>{item.label}</strong>
							{#if item.detail}
								<small>{item.detail}</small>
							{/if}
						</div>
						<div class="tissue-controls">
							<div class="scale-chips" role="group" aria-label={`${item.label} soreness level`}>
								{#each SCALE_LEVELS as level}
									<button
										type="button"
										class="chip"
										class:selected={scaleMap[item.id] === level}
										aria-pressed={scaleMap[item.id] === level}
										onclick={() => selectScale(item.id, level)}
									>
										{level}
									</button>
								{/each}
							</div>
							<button
								type="button"
								class="flag-btn"
								class:flagged={flaggedMap[item.id]}
								aria-pressed={flaggedMap[item.id]}
								title="pain above background noise"
								onclick={() => toggleFlag(item.id)}
							>
								<svg viewBox="0 0 16 16" width="12" height="12" fill="none" aria-hidden="true">
									<path
										d="M4 1.5v13"
										stroke="currentColor"
										stroke-width="1.4"
										stroke-linecap="round"
									/>
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
				{:else}
					<div class="check-item-wrap">
						<label class="check-item">
							<input type="checkbox" bind:checked={checkedMap[item.id]} onchange={emit} />
							<div>
								<strong>{item.label}</strong>
								{#if item.detail}
									<small>{item.detail}</small>
								{/if}
							</div>
						</label>
						{#if checkedMap[item.id]}
							<input
								type="text"
								class="item-text"
								bind:value={textMap[item.id]}
								placeholder="Notes for this item…"
								onblur={emit}
							/>
						{/if}
					</div>
				{/if}
			{/each}
		</div>
	{/if}
{/if}

<style>
	.detail-copy {
		margin: 0;
		color: #a7bac6;
		font-size: 13px;
		line-height: 1.5;
	}

	.detail-list {
		display: grid;
		gap: 6px;
	}

	.detail-row {
		display: flex;
		align-items: center;
		gap: 10px;
		padding: 8px 10px;
		border-radius: 8px;
		background: rgba(255, 255, 255, 0.03);
		font-size: 13px;
	}

	.detail-row-content {
		min-width: 0;
	}

	.detail-row-content strong {
		display: block;
		font-size: 13px;
	}

	.detail-row-content small {
		display: block;
		margin-top: 2px;
		color: #6b8292;
		font-size: 11px;
	}

	.checklist {
		display: grid;
		gap: 6px;
	}

	.check-item-wrap {
		display: grid;
		gap: 4px;
	}

	.check-item {
		display: grid;
		grid-template-columns: auto minmax(0, 1fr);
		align-items: start;
		gap: 10px;
		padding: 8px 10px;
		border-radius: 8px;
		background: rgba(255, 255, 255, 0.03);
		font-size: 13px;
		cursor: pointer;
	}

	.check-item strong {
		font-size: 13px;
	}

	.check-item small {
		display: block;
		margin-top: 2px;
		color: #6b8292;
		font-size: 11px;
	}

	.item-text {
		border: 1px solid rgba(255, 255, 255, 0.1);
		background: rgba(8, 15, 24, 0.7);
		color: #eef5f8;
		border-radius: 8px;
		padding: 6px 10px;
		font: inherit;
		font-size: 12px;
		width: 100%;
		box-sizing: border-box;
	}

	/* ── tissue_check — view mode summary ─────────────────────────────────── */
	.tissue-view-row {
		justify-content: space-between;
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

	/* ── tissue_check — log mode row ──────────────────────────────────────── */
	.tissue-row {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 10px;
		padding: 8px 10px;
		border-radius: 8px;
		background: rgba(255, 255, 255, 0.03);
	}

	.tissue-label-wrap {
		min-width: 0;
	}

	.tissue-label-wrap strong {
		display: block;
		font-size: 13px;
	}

	.tissue-label-wrap small {
		display: block;
		margin-top: 2px;
		color: #6b8292;
		font-size: 11px;
	}

	.tissue-controls {
		display: flex;
		align-items: center;
		gap: 8px;
		flex-shrink: 0;
	}

	/* 0-3 soreness chips — fixed width so selecting one never shifts layout */
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
