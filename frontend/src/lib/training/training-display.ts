/**
 * Small display helpers for v3 training cards on Today/Schedule — the training-domain
 * counterpart of `$lib/routines/card-payloads.ts`. `TrainingTodayCard` never carries a
 * `domain`/`tags` concept like the legacy routine payload union does, so accent/icon/brief
 * are derived structurally from which display arrays the card actually populated
 * (`exercises_display`, `segments_display`, `checkin_rows`) rather than from a declared
 * card type. Both Today and Schedule import this so the two boards render training rows
 * identically.
 */
import type { TrainingTodayCard } from '$lib/api';
import { COLORS, DARK_MUTED_TEXT } from '$lib/colors';

export type TrainingCardTheme = { accent: string; icon: string };

/**
 * Accent color + icon for a training card row, mirroring `domainThemeOf` for routine cards.
 *
 * `checkin_rows` is checked first: `sup.daily` carries both a tissue check-in and its own
 * (small, non-key) segments — e.g. core work — so without this ordering it would theme as a
 * run card. The teal accent matches the calm/recovery palette `card-payloads.ts` uses for
 * breathwork (`COLORS.spo2`) and meditation (`COLORS.hrv`); `COLORS.respiration` is this
 * module's equivalent for the daily body check-in.
 */
export function trainingCardTheme(card: TrainingTodayCard): TrainingCardTheme {
	if (card.checkin_rows.length > 0) return { accent: COLORS.respiration, icon: '📋' };
	if (card.exercises_display.length > 0) return { accent: COLORS.skinTemp, icon: '🏋' };
	if (card.segments_display.length > 0) return { accent: COLORS.heartRate, icon: '🏃' };
	return { accent: DARK_MUTED_TEXT, icon: '' };
}

/** Compact metadata brief for a training card row, mirroring `cardBrief` for routine cards. */
export function trainingCardBrief(card: TrainingTodayCard): string {
	if (card.checkin_rows.length > 0) return `${card.checkin_rows.length} items`;
	if (card.exercises_display.length > 0) return `${card.exercises_display.length} exercises`;
	if (card.segments_display.length > 0) return `${card.segments_display.length} segments`;
	if (card.est_duration_min) return `${card.est_duration_min} min`;
	return '';
}
