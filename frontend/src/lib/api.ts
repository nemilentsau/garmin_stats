/**
 * API client for Garmin Stats backend
 *
 * Type definitions are generated from the FastAPI OpenAPI spec.
 * To regenerate: bash scripts/generate-api-types.sh
 */

import createClient from 'openapi-fetch';
import type { components, paths } from './api-types';
import { API_BASE } from './config';
import { DEFAULT_HRV_BASELINE_WINDOW } from './hrv-baseline';

type Schemas = components['schemas'];

const client = createClient<paths>({
	baseUrl: API_BASE,
	cache: 'no-store'
});

// Re-export generated types with existing frontend names
export type HeartRateRawData = Schemas['HeartRateRawResponse'];
export type StressRawData = Schemas['StressRawResponse'];
export type BodyBatteryRawData = Schemas['BodyBatteryRawResponse'];
export type SpO2RawData = Schemas['SpO2RawResponse'];
export type RespirationRawData = Schemas['RespirationRawResponse'];
export type SleepData = Schemas['SleepResponse'];
export type DailyAggregates = Schemas['DailyAggregatesResponse'];
export type HeartRateDaily = Schemas['HeartRateDailyResponse'];
export type HrvDaily = Schemas['HrvDailyResponse'];
export type SleepDaily = Schemas['SleepDailyResponse'];
export type StressDaily = Schemas['StressDailyResponse'];
export type BodyBatteryDaily = Schemas['BodyBatteryDailyResponse'];
export type RespirationDaily = Schemas['RespirationDailyResponse'];
export type SpO2Daily = Schemas['SpO2DailyResponse'];
export type SkinTempDaily = Schemas['SkinTempDailyResponse'];
export type IngestStatus = Schemas['IngestStatus'];
export type SyncResult = Schemas['SyncResult'];

export type HRAnalysis = Schemas['HeartRateAnalysisResponse'];
export type HRDistribution = Schemas['HRDistributionResponse'];
export type HrvAnalysis = Schemas['HrvAnalysisResponse'];

export type HeartRateInsights = Schemas['HeartRateInsightsResponse'];
export type HrvInsights = Schemas['HrvInsightsResponse'];
export type DashboardOverview = Schemas['DashboardOverviewResponse'];

export type SleepAnalysis = Schemas['SleepAnalysisResponse'];
export type StressAnalysis = Schemas['StressAnalysisResponse'];
export type BodyBatteryAnalysis = Schemas['BodyBatteryAnalysisResponse'];
export type ExperimentInput = Schemas['Experiment-Input'];
export type ExperimentsResponse = Schemas['ExperimentsResponse'];
export type ExperimentWithAnalysis = Schemas['ExperimentWithAnalysis'];
export type ExperimentAnalysis = Schemas['ExperimentAnalysis'];
export type ExperimentPreviewResponse = Schemas['ExperimentPreviewResponse'];
export type MetricAnalysis = Schemas['MetricAnalysis'];
export type MetricLagResult = Schemas['MetricLagResult'];
export type ConfounderCheck = Schemas['ConfounderCheck'];
export type AdherenceDayEntry = Schemas['AdherenceDayEntry'];
export type ExperimentExposureCreate = Schemas['ExperimentExposureCreate'];
export type ImportPackageRequest = Schemas['ImportPackageRequest'];
export type ImportResult = Schemas['ImportResult'];
export type TrainingBlockStatus = Schemas['TrainingBlockStatus'];
export type TrainingTodayCard = Schemas['TrainingTodayCard'];
export type TrainingTodayResponse = Schemas['TrainingTodayResponse'];
export type TrainingScheduleWindow = Schemas['TrainingScheduleWindow'];
export type TrainingCaptureLog = Schemas['TrainingCaptureLog-Output'];
export type TrainingLogUpdateRequest = Schemas['TrainingLogUpdateRequest'];
export type TrainingExerciseDisplay = Schemas['TrainingExerciseDisplay'];
export type TrainingCheckinRow = Schemas['TrainingCheckinRow'];
export type TrainingExerciseLog = Schemas['TrainingExerciseLog-Output'];
export type TrainingSetLog = Schemas['TrainingSetLog-Output'];
export type RunListItem = Schemas['RunListItem'];
export type RunDetail = Schemas['RunDetailResponse'];
export type RunSeries = Schemas['RunSeriesResponse'];
export type CoachStatus = Schemas['CoachStatusResponse'];
export type CoachReview = Schemas['CoachReview'];
export type CoachReviewRevision = Schemas['CoachReviewRevision'];
export type CoachThread = Schemas['CoachThread'];
export type CoachMessage = Schemas['CoachMessage'];
export type CoachBriefResponse = Schemas['CoachBriefResponse'];
export type CoachJournalResponse = Schemas['CoachJournalResponse'];
export type JournalEntry = Schemas['JournalEntry'];
export type CoachWatchItem = Schemas['CoachWatchItem'];

function apiErrorMessage(body: unknown): string {
	if (
		typeof body === 'object' &&
		body !== null &&
		'detail' in body &&
		typeof body.detail === 'string'
	) {
		return body.detail;
	}
	return typeof body === 'string' ? body : JSON.stringify(body);
}

export class ApiError extends Error {
	readonly status: number;
	readonly body: unknown;

	constructor(status: number, body: unknown) {
		super(apiErrorMessage(body));
		this.name = 'ApiError';
		this.status = status;
		this.body = body;
	}
}

type ApiResponse<T> = Promise<{ data?: T; error?: unknown; response: Response }>;

async function unwrapResponse<T>(response: ApiResponse<T>): Promise<T> {
	const { data, error, response: rawResponse } = await response;
	if (error !== undefined) {
		throw new ApiError(rawResponse.status, error);
	}
	if (data === undefined) {
		throw new Error('API response did not include JSON data');
	}
	return data;
}

const dateQuery = (date?: string) => ({ params: { query: date ? { date } : {} } });

export const api = {
	getDailyAggregates: async () => {
		return unwrapResponse(client.GET('/api/daily-aggregates'));
	},
	getDashboardOverview: async () => {
		return unwrapResponse(client.GET('/api/dashboard'));
	},
	getHeartRateDaily: async () => {
		return unwrapResponse(client.GET('/api/heart-rate/daily'));
	},
	getHrvDaily: async () => {
		return unwrapResponse(client.GET('/api/hrv/daily'));
	},
	getSleepDaily: async () => {
		return unwrapResponse(client.GET('/api/sleep/daily'));
	},
	getStressDaily: async () => {
		return unwrapResponse(client.GET('/api/stress/daily'));
	},
	getBodyBatteryDaily: async () => {
		return unwrapResponse(client.GET('/api/body-battery/daily'));
	},
	getRespirationDaily: async () => {
		return unwrapResponse(client.GET('/api/respiration/daily'));
	},
	getPulseOxDaily: async () => {
		return unwrapResponse(client.GET('/api/pulse-ox/daily'));
	},
	getSkinTempDaily: async () => {
		return unwrapResponse(client.GET('/api/skin-temp/daily'));
	},
	getHeartRateRaw: async (date?: string) => {
		return unwrapResponse(client.GET('/api/heart-rate/raw', dateQuery(date)));
	},
	getStressRaw: async (date?: string) => {
		return unwrapResponse(client.GET('/api/stress/raw', dateQuery(date)));
	},
	getBodyBatteryRaw: async (date?: string) => {
		return unwrapResponse(client.GET('/api/body-battery/raw', dateQuery(date)));
	},
	getPulseOxRaw: async (date?: string) => {
		return unwrapResponse(client.GET('/api/pulse-ox/raw', dateQuery(date)));
	},
	getRespirationRaw: async (date?: string) => {
		return unwrapResponse(client.GET('/api/respiration/raw', dateQuery(date)));
	},
	getSleepRaw: async (date?: string) => {
		return unwrapResponse(client.GET('/api/sleep/raw', dateQuery(date)));
	},
	getHrvInsights: async (date?: string, baseline = DEFAULT_HRV_BASELINE_WINDOW) => {
		return unwrapResponse(client.GET('/api/hrv/insights', { params: { query: { date, baseline: baseline as Schemas['BaselineWindow'] } } }));
	},
	getHrvAnalysis: async (baseline = DEFAULT_HRV_BASELINE_WINDOW) => {
		return unwrapResponse(client.GET('/api/hrv/analysis', { params: { query: { baseline: baseline as Schemas['BaselineWindow'] } } }));
	},
	getHeartRateInsights: async (date?: string) => {
		return unwrapResponse(client.GET('/api/heart-rate/insights', dateQuery(date)));
	},
	getHeartRateAnalysis: async () => {
		return unwrapResponse(client.GET('/api/heart-rate/analysis'));
	},
	getHRDistribution: async (date: string) => {
		return unwrapResponse(client.GET('/api/heart-rate/distribution', {
			params: { query: { date } }
		}));
	},
	triggerSync: async () => {
		return unwrapResponse(client.POST('/api/ingest/sync'));
	},
	getIngestStatus: async () => {
		return unwrapResponse(client.GET('/api/ingest/status'));
	},
	getSleepAnalysis: async () => {
		return unwrapResponse(client.GET('/api/sleep/analysis'));
	},
	getStressAnalysis: async () => {
		return unwrapResponse(client.GET('/api/stress/analysis'));
	},
	getBodyBatteryAnalysis: async () => {
		return unwrapResponse(client.GET('/api/body-battery/analysis'));
	},
	getExperiments: async () => {
		return unwrapResponse(client.GET('/api/experiments'));
	},
	getExperiment: async (experimentId: string) => {
		return unwrapResponse(client.GET('/api/experiments/{experiment_id}', {
			params: { path: { experiment_id: experimentId } }
		}));
	},
	previewExperiment: async (experiment: ExperimentInput) => {
		return unwrapResponse(client.POST('/api/experiments/preview', { body: experiment }));
	},
	importExperiment: async (experiment: ExperimentInput) => {
		return unwrapResponse(client.POST('/api/experiments/import', { body: experiment }));
	},
	recordExperimentExposure: async (experimentId: string, exposure: ExperimentExposureCreate) => {
		return unwrapResponse(client.POST('/api/experiments/{experiment_id}/exposures', {
			params: { path: { experiment_id: experimentId } },
			body: exposure
		}));
	},
	importTraining: async (body: ImportPackageRequest) => {
		return unwrapResponse(client.POST('/api/training/import', { body }));
	},
	getTrainingBlock: async () => {
		return unwrapResponse(client.GET('/api/training/block'));
	},
	getTrainingToday: async (date: string) => {
		return unwrapResponse(client.GET('/api/training/today', {
			params: { query: { date } }
		}));
	},
	getTrainingScheduleWindow: async (start: string, days = 14) => {
		return unwrapResponse(client.GET('/api/training/schedule-window', {
			params: { query: { start, days } }
		}));
	},
	updateTrainingCard: async (date: string, occurrenceKey: string, payload: TrainingLogUpdateRequest) => {
		return unwrapResponse(client.PUT('/api/training/today/{date}/cards/{occurrence_key}', {
			params: { path: { date, occurrence_key: occurrenceKey } },
			body: payload
		}));
	},
	getRuns: async (from?: string, to?: string) => {
		return unwrapResponse(client.GET('/api/activities/runs', {
			params: { query: { ...(from ? { from } : {}), ...(to ? { to } : {}) } }
		}));
	},
	getRun: async (runId: string) => {
		return unwrapResponse(client.GET('/api/activities/runs/{run_id}', {
			params: { path: { run_id: runId } }
		}));
	},
	getRunSeries: async (runId: string) => {
		return unwrapResponse(client.GET('/api/activities/runs/{run_id}/series', {
			params: { path: { run_id: runId } }
		}));
	},
	getCoachStatus: async () => unwrapResponse(client.GET('/api/coach/status')),
	coachPlotUrl: (plotName: string) => `${API_BASE}/api/coach/plots/${encodeURIComponent(plotName)}`,
	getCoachReviews: async (params?: { from?: string; to?: string; limit?: number }) => {
		return unwrapResponse(client.GET('/api/coach/reviews', {
			params: { query: params ?? {} }
		}));
	},
	getCoachRunReview: async (runId: string) => {
		return unwrapResponse(client.GET('/api/coach/run-reviews/{run_id}', {
			params: { path: { run_id: runId } }
		}));
	},
	enqueueCoachDayReview: async (date: string) => {
		return unwrapResponse(client.POST('/api/coach/reviews/day', { body: { date } }));
	},
	enqueueCoachWeekReview: async (weekStart: string) => {
		return unwrapResponse(
			client.POST('/api/coach/reviews/week', { body: { week_start: weekStart } })
		);
	},
	retryCoachReview: async (reviewId: string) => {
		return unwrapResponse(client.POST('/api/coach/reviews/{review_id}/retry', {
			params: { path: { review_id: reviewId } }
		}));
	},
	openCoachReviewThread: async (reviewId: string) => {
		return unwrapResponse(client.POST('/api/coach/reviews/{review_id}/thread', {
			params: { path: { review_id: reviewId } }
		}));
	},
	getCoachReviewThread: async (reviewId: string) => {
		return unwrapResponse(client.GET('/api/coach/reviews/{review_id}/thread', {
			params: { path: { review_id: reviewId } }
		}));
	},
	getCoachReviewRevisions: async (reviewId: string) => {
		return unwrapResponse(client.GET('/api/coach/reviews/{review_id}/revisions', {
			params: { path: { review_id: reviewId } }
		}));
	},
	getCoachThreads: async () => unwrapResponse(client.GET('/api/coach/threads')),
	createCoachThread: async (title: string) => {
		return unwrapResponse(client.POST('/api/coach/threads', { body: { title } }));
	},
	getCoachMessages: async (threadId: string) => {
		return unwrapResponse(client.GET('/api/coach/threads/{thread_id}/messages', {
			params: { path: { thread_id: threadId } }
		}));
	},
	sendCoachMessage: async (
		threadId: string,
		contentMd: string,
		reviewRevisionRequested = false
	) => {
		return unwrapResponse(client.POST('/api/coach/threads/{thread_id}/messages', {
			params: { path: { thread_id: threadId } },
			body: {
				content_md: contentMd,
				review_revision_requested: reviewRevisionRequested
			}
		}));
	},
	closeCoachThread: async (threadId: string) => {
		return unwrapResponse(client.POST('/api/coach/threads/{thread_id}/close', {
			params: { path: { thread_id: threadId } }
		}));
	},
	retryCoachThreadClose: async (threadId: string) => {
		return unwrapResponse(client.POST('/api/coach/threads/{thread_id}/retry-close', {
			params: { path: { thread_id: threadId } }
		}));
	},
	getCoachBrief: async () => unwrapResponse(client.GET('/api/coach/brief')),
	getCoachJournal: async (limit = 30) => {
		return unwrapResponse(client.GET('/api/coach/journal', { params: { query: { limit } } }));
	},
};
