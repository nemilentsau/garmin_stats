<script lang="ts">
	/**
	 * CardBody — dispatches to the card-type-specific component for a single occurrence.
	 *
	 * Currently wired:
	 *   checklist        → ChecklistCard        (Phase 2)
	 *   breath_timer     → BreathTimerCard       (Phase 3)
	 *   meditation_timer → MeditationTimerCard   (Phase 3)
	 *   strength_session → StrengthSessionCard   (Phase 4)
	 *   all other types  → TEMPORARY inline fallback, replaced in Phase 5
	 *
	 * Props:
	 *   card   — ScheduleOccurrence or TodayCard shape (both have payload_json; TodayCard adds
	 *            actual_json for pre-fill).
	 *   mode   — 'log' (Today board, user can enter actuals) | 'view' (Schedule, read-only).
	 *   onActual — callback fired whenever the user changes log state; only used in 'log' mode.
	 *              The parent is responsible for stashing + persisting the emitted value.
	 */
	import type { ScheduleOccurrence, TodayCard } from '$lib/api';
	import ChecklistCard from './ChecklistCard.svelte';
	import BreathTimerCard from './BreathTimerCard.svelte';
	import MeditationTimerCard from './MeditationTimerCard.svelte';
	import StrengthSessionCard from './StrengthSessionCard.svelte';

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
</script>

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
{:else if card.payload_json.card_type === 'strength_session'}
	<!--
		StrengthSessionCard is fully implemented (Phase 4).
		payload_json is narrowed to StrengthSessionPayload by the type guard above.
	-->
	<StrengthSessionCard
		card={{ payload_json: card.payload_json, actual_json: card.actual_json }}
		{mode}
		{onActual}
	/>
{:else}
	<!-- TEMPORARY fallback — dedicated component replaces this block in Phase 5.
	     Remaining type: running_workout. -->

	{#if card.payload_json.instructions}
		<p class="detail-copy">{card.payload_json.instructions}</p>
	{/if}
{/if}

<style>
	.detail-copy {
		margin: 0;
		color: #a7bac6;
		font-size: 13px;
		line-height: 1.5;
	}
</style>
