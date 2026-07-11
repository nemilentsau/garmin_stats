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

/**
 * The card's "next move" for the collapsed row: the anchor lift plus how many more for a
 * strength card, the lead segment for a run — so the face states what you'd actually do
 * first, not a bare count. Check-in is listed first for the same reason as `trainingCardTheme`
 * (sup.daily carries both a check-in and small segments).
 */
export function trainingCardBrief(card: TrainingTodayCard): string {
	if (card.checkin_rows.length > 0) return `check-in · ${card.checkin_rows.length} tissues`;
	if (card.exercises_display.length > 0) {
		const [first, ...rest] = card.exercises_display;
		const more = rest.length > 0 ? ` · +${rest.length}` : '';
		return `${first.name} ${exerciseTarget(first)}${more}`;
	}
	if (card.segments_display.length > 0) {
		const [first, ...rest] = card.segments_display;
		const more = rest.length > 0 ? ` · +${rest.length}` : '';
		return `${first.detail || first.label}${more}`;
	}
	if (card.est_duration_min) return `${card.est_duration_min} min`;
	return '';
}

/** Compact "sets×reps @load" for one exercise, from its structured display fields. */
function exerciseTarget(ex: TrainingTodayCard['exercises_display'][number]): string {
	const reps = ex.reps_low === ex.reps_high ? `${ex.reps_low}` : `${ex.reps_low}–${ex.reps_high}`;
	const base = `${ex.sets}×${reps}`;
	if (ex.load_kind === 'rpe' && ex.load_value != null) return `${base} @${ex.load_value}`;
	if (ex.load_kind === 'pct_e1rm' && ex.load_value != null) return `${base} @${Math.round(ex.load_value * 100)}%`;
	if (ex.load_kind === 'absolute_kg' && ex.load_value != null) return `${base} ${ex.load_value}kg`;
	return base;
}
