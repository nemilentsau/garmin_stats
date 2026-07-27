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
	 * even though the latest authored v3 program doesn't do so today (see
	 * `docs/training/programs/threshold-development-2026-07-13/threshold-development-2026-07-13.zip`,
	 * member `support_v3.json`).
	 */
	import { untrack } from 'svelte';
	import type { TrainingCaptureLog, TrainingCheckinRow } from '$lib/api';
	import TissueCheckRow from '$lib/today/TissueCheckRow.svelte';

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

	function emit() {
		onCheckin?.({
			soreness: Object.fromEntries(rows.map((row) => [row.tissue, scaleMap[row.tissue] ?? 0])),
			flags: Object.fromEntries(rows.map((row) => [row.tissue, flaggedMap[row.tissue] ?? false])),
			core_done: coreDone
		});
	}

	function selectScale(tissue: string, level: number) {
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
			<TissueCheckRow label={row.label} mode="view" {scale} {flagged} />
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
			<TissueCheckRow
				label={row.label}
				mode="log"
				scale={scaleMap[row.tissue] ?? 0}
				flagged={flaggedMap[row.tissue] ?? false}
				onSelectScale={(level) => selectScale(row.tissue, level)}
				onToggleFlag={() => toggleFlag(row.tissue)}
			/>
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
