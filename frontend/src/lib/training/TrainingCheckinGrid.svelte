<script lang="ts">
	/**
	 * TrainingCheckinGrid — daily tissue soreness check-in for the v3 support card
	 * (`sup.daily`'s `cap.checkin.soreness` / `cap.checkin.flags` / `cap.checkin.core_done`
	 * capture fields).
	 *
	 * Interaction mirrors ChecklistCard's `tissue_check` rows exactly: a 0-3 soreness scale
	 * plus a "pain above background noise" flag per tissue, seeded once (untrack, house
	 * pattern — component is freshly mounted whenever the detail panel opens) from
	 * `card.capture.checkin`. Adds one core_done checkbox row alongside the per-tissue rows.
	 *
	 * Capture ownership: this component owns ONLY `checkin`. It emits just that slice via
	 * `onCheckin` on every change and never reads or replays `set_logs`/`rpe` — TrainingCardBody
	 * composes the full TrainingCaptureLog from each child's slice. This is deliberate: a
	 * component that seeds a sibling capture kind once and replays it unchanged on every emit
	 * would silently revert that sibling's staged edits if a card ever combined capture kinds,
	 * even though the shipped v3 bundles don't do so today (see
	 * `docs/routine-pivot/block0/support_v3.json`).
	 */
	import { untrack } from 'svelte';
	import type { TrainingCaptureLog, TrainingCheckinRow } from '$lib/api';

	let {
		card,
		mode,
		onCheckin
	}: {
		card: { checkin_rows: TrainingCheckinRow[]; capture: TrainingCaptureLog | null };
		mode: 'log' | 'view';
		onCheckin?: (checkin: TrainingCaptureLog['checkin']) => void;
	} = $props();

	const rows = $derived(card.checkin_rows);

	// ── One-time synchronous init — see TrainingStrengthGrid for the same house pattern. ──
	const initialRows = untrack(() => card.checkin_rows);
	const initialCapture = untrack(() => card.capture);
	const initialCheckin = initialCapture?.checkin ?? null;

	// scale defaults to 0 (visually "no soreness") when nothing was ever stored — a real,
	// persistable value rather than a null placeholder, mirroring ChecklistCard's scaleMap.
	let scaleMap = $state<Record<string, number>>(
		Object.fromEntries(initialRows.map((row) => [row.tissue, initialCheckin?.soreness[row.tissue] ?? 0]))
	);
	let flaggedMap = $state<Record<string, boolean>>(
		Object.fromEntries(initialRows.map((row) => [row.tissue, initialCheckin?.flags[row.tissue] ?? false]))
	);
	let coreDone = $state<boolean>(initialCheckin?.core_done ?? false);

	const SCALE_LEVELS = [0, 1, 2, 3] as const;

	function emit() {
		onCheckin?.({
			soreness: Object.fromEntries(rows.map((row) => [row.tissue, scaleMap[row.tissue] ?? 0])),
			flags: Object.fromEntries(rows.map((row) => [row.tissue, flaggedMap[row.tissue] ?? false])),
			core_done: coreDone
		});
	}

	function selectScale(tissue: string, level: (typeof SCALE_LEVELS)[number]) {
		scaleMap[tissue] = level;
		emit();
	}

	function toggleFlag(tissue: string) {
		flaggedMap[tissue] = !flaggedMap[tissue];
		emit();
	}

	function toggleCore() {
		coreDone = !coreDone;
		emit();
	}
</script>

{#if mode === 'view'}
	<div class="detail-list">
		{#each rows as row}
			{@const scale = initialCheckin && row.tissue in initialCheckin.soreness ? initialCheckin.soreness[row.tissue] : null}
			{@const flagged = initialCheckin?.flags[row.tissue] ?? false}
			<div class="detail-row tissue-view-row">
				<div class="detail-row-content"><strong>{row.label}</strong></div>
				{#if scale !== null}
					<span class="tissue-summary">{scale}{#if flagged}&nbsp;⚑{/if}</span>
				{:else}
					<span class="tissue-summary unanswered">–</span>
				{/if}
			</div>
		{/each}
		{#if rows.length > 0}
			{@const coreVal = initialCheckin?.core_done ?? null}
			<div class="detail-row tissue-view-row">
				<div class="detail-row-content"><strong>Core</strong></div>
				{#if coreVal !== null}
					<span class="tissue-summary">{coreVal ? 'done' : 'not done'}</span>
				{:else}
					<span class="tissue-summary unanswered">–</span>
				{/if}
			</div>
		{/if}
	</div>
{:else}
	<div class="checklist">
		{#each rows as row}
			<div class="tissue-row">
				<div class="tissue-label-wrap"><strong>{row.label}</strong></div>
				<div class="tissue-controls">
					<div class="scale-chips" role="group" aria-label={`${row.label} soreness level`}>
						{#each SCALE_LEVELS as level}
							<button
								type="button"
								class="chip"
								class:selected={scaleMap[row.tissue] === level}
								aria-pressed={scaleMap[row.tissue] === level}
								onclick={() => selectScale(row.tissue, level)}
							>
								{level}
							</button>
						{/each}
					</div>
					<button
						type="button"
						class="flag-btn"
						class:flagged={flaggedMap[row.tissue]}
						aria-pressed={flaggedMap[row.tissue]}
						title="pain above background noise"
						onclick={() => toggleFlag(row.tissue)}
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
		{/each}
		{#if rows.length > 0}
			<label class="core-check">
				<input type="checkbox" checked={coreDone} onchange={toggleCore} />
				<span>Core done</span>
			</label>
		{/if}
	</div>
{/if}

<style>
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

	.checklist {
		display: grid;
		gap: 6px;
	}

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

	.core-check {
		display: flex;
		align-items: center;
		gap: 8px;
		padding: 8px 10px;
		border-radius: 8px;
		background: rgba(255, 255, 255, 0.03);
		font-size: 13px;
		color: #c3d3dd;
		cursor: pointer;
	}
</style>
