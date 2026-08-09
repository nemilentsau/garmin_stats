import type { components } from '$lib/api-types';

export type ReviewOutcome = components['schemas']['CoachReview']['outcome'];
export type MeasurementStatus = components['schemas']['TrainingMeasurementEvaluation']['status'];

/** One vocabulary for coach judgments, shared by /coach and Today cards.
 *  Session (stimulus) and Measurement (validity) are separate axes. */
export const SESSION_LABELS: Record<NonNullable<ReviewOutcome>, string> = {
	completed_as_intended: 'Went as planned',
	completed_with_material_deviation: 'Useful work, off-plan',
	not_completed: 'Not completed',
	skipped: 'Skipped',
	unplanned: 'Unplanned session'
};

export const MEASUREMENT_LABELS: Record<MeasurementStatus, string> = {
	awaiting_review: 'Measurement: awaiting review',
	valid: 'Measurement: valid',
	provisional: 'Measurement: provisional',
	failed: 'Measurement: not valid — zones unchanged'
};

export function sessionLabel(outcome: ReviewOutcome | null | undefined): string {
	return outcome ? SESSION_LABELS[outcome] : 'Not assessed';
}

export function measurementLabel(status: MeasurementStatus): string {
	return MEASUREMENT_LABELS[status];
}
