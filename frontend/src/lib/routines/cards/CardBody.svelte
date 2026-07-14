<script lang="ts">
	/**
	 * CardBody — dispatches to the card-type-specific component for a single occurrence.
	 *
	 * The legacy v2 runtime supports the non-training card types that remain importable:
	 *   checklist        → ChecklistCard        (Phase 2)
	 *   breath_timer     → BreathTimerCard       (Phase 3)
	 *   meditation_timer → MeditationTimerCard   (Phase 3)
	 *
	 * Props:
	 *   card   — ScheduleOccurrence or TodayCard shape (both have payload_json; TodayCard adds
	 *            actual_json for pre-fill).
	 *   mode   — 'log' (Today board, user can enter actuals) | 'view' (Schedule, read-only).
	 *   onActual — callback fired whenever the user changes log state; only used in 'log' mode.
	 *              The parent is responsible for stashing + persisting the emitted value.
	 *
	 * Also renders a display-only "Rule: …" line under the card header (both modes) when the
	 * occurrence's checklist payload carries a non-null `selection_rule`. No logic here:
	 * this is a pass-through of a backend-generated string.
	 */
	import type { ScheduleOccurrence, TodayCard } from '$lib/api';
	import ChecklistCard from './ChecklistCard.svelte';
	import BreathTimerCard from './BreathTimerCard.svelte';
	import MeditationTimerCard from './MeditationTimerCard.svelte';

	type CardPayload = ScheduleOccurrence['payload_json'];
	type CardActual = NonNullable<TodayCard['actual_json']>;

	let {
		card,
		mode,
		onActual
	}: {
		card: {
			name: string;
			summary?: string | null;
			payload_json: CardPayload;
			actual_json?: TodayCard['actual_json'];
		};
		mode: 'log' | 'view';
		onActual?: (actual: CardActual) => void;
	} = $props();

	// Only checklist payloads carry selection_rule in the retained v2 contract.
	const selectionRule = $derived(
		'selection_rule' in card.payload_json ? card.payload_json.selection_rule : null
	);
</script>

{#if selectionRule}
	<p class="rule-line">Rule: {selectionRule}</p>
{/if}

{#if card.payload_json.card_type === 'checklist'}
	<!--
		ChecklistCard is fully implemented (Phase 2).
		payload_json is narrowed to ChecklistPayload by the type guard above.
	-->
	<ChecklistCard
		card={{ payload_json: card.payload_json, actual_json: card.actual_json }}
		{mode}
		{onActual}
	/>
{:else if card.payload_json.card_type === 'breath_timer'}
	<!--
		BreathTimerCard is fully implemented (Phase 3).
		payload_json is narrowed to BreathTimerPayload by the type guard above.
	-->
	<BreathTimerCard
		card={{ payload_json: card.payload_json, actual_json: card.actual_json }}
		{mode}
		{onActual}
	/>
{:else if card.payload_json.card_type === 'meditation_timer'}
	<!--
		MeditationTimerCard is fully implemented (Phase 3).
		payload_json is narrowed to MeditationTimerPayload by the type guard above.
	-->
	<MeditationTimerCard
		card={{ payload_json: card.payload_json, actual_json: card.actual_json }}
		{mode}
		{onActual}
	/>
{/if}

<style>
	.rule-line {
		margin: 0 0 10px;
		color: #6b8292;
		font-size: 11px;
		font-family: 'DM Mono', monospace;
		letter-spacing: 0.02em;
		line-height: 1.5;
	}
</style>
