import type { ScheduleOccurrence } from '$lib/api';
import { COLORS, DARK_MUTED_TEXT, withAlpha } from '$lib/colors';
import { isRecord } from '$lib/utils';

export type SlotAccent = { color: string; shadow: string };
export type SlotName = ScheduleOccurrence['slot'];
export type Renderer = ScheduleOccurrence['renderer'];

export type TimerPayload = {
	duration_minutes?: number;
	pattern?: string;
	instructions?: string;
	segments?: { label: string; duration_seconds: number }[];
	rating_prompts?: { key: string; label: string; scale_min?: number; scale_max?: number }[];
};

export type ChecklistPayload = {
	instructions?: string;
	items?: { id: string; label: string; detail?: string }[];
};

export type ExercisePayload = {
	instructions?: string;
	exercises?: {
		id: string;
		label: string;
		detail?: string;
		reps?: string;
		duration_seconds?: number;
	}[];
};

export const SLOT_ORDER: readonly SlotName[] = ['morning', 'midday', 'evening', 'anytime'];

export const SLOT_LABELS: Record<SlotName, string> = {
	morning: 'Morning',
	midday: 'Midday',
	evening: 'Evening',
	anytime: 'Anytime'
};

export const SLOT_ACCENTS: Record<SlotName, SlotAccent> = {
	morning: { color: COLORS.respiration, shadow: withAlpha(COLORS.respiration, '30') },
	midday: { color: COLORS.spo2, shadow: withAlpha(COLORS.spo2, '30') },
	evening: { color: COLORS.hrv, shadow: withAlpha(COLORS.hrv, '30') },
	anytime: { color: COLORS.stress, shadow: withAlpha(COLORS.stress, '30') }
};

export const DEFAULT_SLOT_ACCENT: SlotAccent = {
	color: DARK_MUTED_TEXT,
	shadow: withAlpha(DARK_MUTED_TEXT, '30')
};

export function slotAccent(slot: SlotName): SlotAccent {
	return SLOT_ACCENTS[slot] ?? DEFAULT_SLOT_ACCENT;
}

export function timerPayload(payload: unknown): TimerPayload {
	return isRecord(payload) ? (payload as TimerPayload) : {};
}

export function checklistPayload(payload: unknown): ChecklistPayload {
	return isRecord(payload) ? (payload as ChecklistPayload) : {};
}

export function exercisePayload(payload: unknown): ExercisePayload {
	return isRecord(payload) ? (payload as ExercisePayload) : {};
}

export function cardBrief(card: { renderer: Renderer; payload_json: unknown }): string {
	if (card.renderer === 'timer_session') {
		const payload = timerPayload(card.payload_json);
		return payload.duration_minutes ? `${payload.duration_minutes} min` : '';
	}
	if (card.renderer === 'exercise_block') {
		const payload = exercisePayload(card.payload_json);
		return payload.exercises?.length ? `${payload.exercises.length} exercises` : '';
	}
	const payload = checklistPayload(card.payload_json);
	return payload.items?.length ? `${payload.items.length} items` : '';
}
