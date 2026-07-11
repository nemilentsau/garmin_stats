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
export type HrvData = Schemas['HrvResponse'];
export type SkinTempData = Schemas['SkinTempResponse'];
export type DailyAggregates = Schemas['DailyAggregatesResponse'];
export type HeartRateDaily = Schemas['HeartRateDailyResponse'];
export type HrvDaily = Schemas['HrvDailyResponse'];
export type SleepDaily = Schemas['SleepDailyResponse'];
export type StressDaily = Schemas['StressDailyResponse'];
export type BodyBatteryDaily = Schemas['BodyBatteryDailyResponse'];
export type RespirationDaily = Schemas['RespirationDailyResponse'];
export type SpO2Daily = Schemas['SpO2DailyResponse'];
export type SkinTempDaily = Schemas['SkinTempDailyResponse'];
export type DailyMetric = Schemas['DailyMetric'];
export type IngestResult = Schemas['IngestResult'];
export type IngestStatus = Schemas['IngestStatus'];
export type SyncResult = Schemas['SyncResult'];
export type DailyHeartRateStats = Schemas['DailyHeartRateStats'];

export type HRAnalysis = Schemas['HeartRateAnalysisResponse'];
export type HRDistribution = Schemas['HRDistributionResponse'];
export type HrvAnalysis = Schemas['HrvAnalysisResponse'];

export type HeartRateInsights = Schemas['HeartRateInsightsResponse'];
export type HrvInsights = Schemas['HrvInsightsResponse'];
export type DashboardOverview = Schemas['DashboardOverviewResponse'];

export type SleepAnalysis = Schemas['SleepAnalysisResponse'];
export type StressAnalysis = Schemas['StressAnalysisResponse'];
export type BodyBatteryAnalysis = Schemas['BodyBatteryAnalysisResponse'];
export type UserProfile = Schemas['UserProfile-Output'];
export type UserProfileInput = Schemas['UserProfile-Input'];
export type DailyCheckIn = Schemas['DailyCheckIn-Output'];
export type DailyCheckInInput = Schemas['DailyCheckIn-Input'];
export type DailyCheckInsResponse = Schemas['DailyCheckInsResponse'];
export type Note = Schemas['Note-Output'];
export type NoteInput = Schemas['Note-Input'];
export type NotesResponse = Schemas['NotesResponse'];
export type TargetMetricDefinition = Schemas['TargetMetricDefinition'];
export type TargetMetricsResponse = Schemas['TargetMetricsResponse'];
export type Experiment = Schemas['Experiment-Output'];
export type ExperimentInput = Schemas['Experiment-Input'];
export type ExperimentsResponse = Schemas['ExperimentsResponse'];
export type ExperimentWithAnalysis = Schemas['ExperimentWithAnalysis'];
export type ExperimentAnalysis = Schemas['ExperimentAnalysis'];
export type ExperimentPreviewResponse = Schemas['ExperimentPreviewResponse'];
export type MetricAnalysis = Schemas['MetricAnalysis'];
export type MetricLagResult = Schemas['MetricLagResult'];
export type ConfounderCheck = Schemas['ConfounderCheck'];
export type AdherenceDayEntry = Schemas['AdherenceDayEntry'];
export type AssistantArtifact = Schemas['AssistantArtifact'];
export type AssistantArtifactInput = Schemas['AssistantArtifactCreateRequest'];
export type AssistantArtifactsResponse = Schemas['AssistantArtifactsResponse'];
export type ArtifactBundleSpec = Schemas['ArtifactBundleSpec'];
export type ArtifactBundlePreviewResponse = Schemas['ArtifactBundlePreviewResponse'];
export type ArtifactBundleImportResponse = Schemas['ArtifactBundleImportResponse'];
export type AssistantThread = Schemas['AssistantThread'];
export type AssistantThreadInput = Schemas['AssistantThreadCreateRequest'];
export type AssistantThreadsResponse = Schemas['AssistantThreadsResponse'];
export type AssistantMessage = Schemas['AssistantMessage'];
export type AssistantMessageInput = Schemas['AssistantMessageCreateRequest'];
export type AssistantMessagesResponse = Schemas['AssistantMessagesResponse'];
export type CardTemplate = Schemas['CardTemplate'];
export type CardTemplatesResponse = Schemas['CardTemplatesResponse'];
export type CardLog = Schemas['CardLog'];
export type CardLogRangeResponse = Schemas['CardLogRangeResponse'];
export type RoutineAssignment = Schemas['RoutineAssignment'];
export type RoutineAssignmentsResponse = Schemas['RoutineAssignmentsResponse'];
export type RoutineSchedule = Schemas['RoutineSchedule'];
export type RoutineSchedulesResponse = Schemas['RoutineSchedulesResponse'];
export type ScheduleDay = Schemas['ScheduleDay'];
export type ScheduleOccurrence = Schemas['ScheduleOccurrence'];
export type ScheduleWindow = Schemas['ScheduleWindow'];
export type TodayCard = Schemas['TodayCard'];
export type TodayCardLogUpdate = Schemas['TodayCardLogUpdateRequest'];
export type TodayResponse = Schemas['TodayResponse'];
export type Program = Schemas['Program'];
export type ProgramsResponse = Schemas['ProgramsResponse'];
export type ProgramVersion = Schemas['ProgramVersion'];
export type ProgramVersionsResponse = Schemas['ProgramVersionsResponse'];
export type ImportFile = Schemas['ImportFile'];
export type ImportRequest = Schemas['ImportRequest'];
export type ImportResult = Schemas['ImportResult'];
export type FileValidation = Schemas['FileValidation'];
export type LintReport = Schemas['LintReport'];
export type TrainingBlockStatus = Schemas['TrainingBlockStatus'];
export type TrainingTodayCard = Schemas['TrainingTodayCard'];
export type TrainingTodayResponse = Schemas['TrainingTodayResponse'];
export type TrainingScheduleDay = Schemas['TrainingScheduleDay'];
export type TrainingScheduleWindow = Schemas['TrainingScheduleWindow'];
export type TrainingCaptureLog = Schemas['TrainingCaptureLog-Output'];
export type TrainingLogUpdateRequest = Schemas['TrainingLogUpdateRequest'];
export type TrainingExerciseDisplay = Schemas['TrainingExerciseDisplay'];
export type TrainingSegmentDisplay = Schemas['TrainingSegmentDisplay'];
export type TrainingCheckinRow = Schemas['TrainingCheckinRow'];
export type TrainingExerciseLog = Schemas['TrainingExerciseLog-Output'];
export type TrainingSetLog = Schemas['TrainingSetLog-Output'];
export type TrainingCheckinLog = Schemas['TrainingCheckinLog-Output'];
export type RunsList = Schemas['RunsListResponse'];
export type RunListItem = Schemas['RunListItem'];
export type RunDetail = Schemas['RunDetailResponse'];
export type RunSeries = Schemas['RunSeriesResponse'];

function unwrap<T>(data: T | undefined, error: unknown): T {
	if (error) {
		throw new Error(typeof error === 'string' ? error : JSON.stringify(error));
	}
	if (data === undefined) {
		throw new Error('API response did not include JSON data');
	}
	return data;
}

type ApiResponse<T> = Promise<{ data?: T; error?: unknown }>;

async function unwrapResponse<T>(response: ApiResponse<T>): Promise<T> {
	const { data, error } = await response;
	return unwrap(data, error);
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
	getHrvRaw: async (date?: string) => {
		return unwrapResponse(client.GET('/api/hrv/raw', dateQuery(date)));
	},
	getSkinTempRaw: async (date?: string) => {
		return unwrapResponse(client.GET('/api/skin-temp/raw', dateQuery(date)));
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
	triggerIngest: async () => {
		return unwrapResponse(client.POST('/api/ingest'));
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
	getProfile: async () => {
		return unwrapResponse(client.GET('/api/profile'));
	},
	updateProfile: async (profile: UserProfileInput) => {
		return unwrapResponse(client.PUT('/api/profile', { body: profile }));
	},
	getRoutines: async (status?: string) => {
		return unwrapResponse(client.GET('/api/routines', {
			params: { query: status ? { status } : {} }
		}));
	},
	getRoutineScheduleWindow: async (startDate: string) => {
		return unwrapResponse(client.GET('/api/routines/schedule-window', {
			params: { query: { start_date: startDate } }
		}));
	},
	getRoutineAssignments: async (routineId: string) => {
		return unwrapResponse(client.GET('/api/routines/{routine_id}/assignments', {
			params: { path: { routine_id: routineId } }
		}));
	},
	getCards: async (status?: string) => {
		return unwrapResponse(client.GET('/api/cards', {
			params: { query: status ? { status } : {} }
		}));
	},
	getToday: async (date: string) => {
		return unwrapResponse(client.GET('/api/today', {
			params: { query: { date } }
		}));
	},
	updateTodayCard: async (date: string, occurrenceKey: string, payload: TodayCardLogUpdate) => {
		return unwrapResponse(client.PUT('/api/today/{date}/cards/{occurrence_key}', {
			params: { path: { date, occurrence_key: occurrenceKey } },
			body: payload
		}));
	},
	getCardLogsRange: async (startDate: string, endDate: string) => {
		return unwrapResponse(client.GET('/api/today/card-logs', {
			params: { query: { start_date: startDate, end_date: endDate } }
		}));
	},
	getCheckins: async (date?: string) => {
		return unwrapResponse(client.GET('/api/checkins', dateQuery(date)));
	},
	createCheckin: async (checkin: DailyCheckInInput) => {
		return unwrapResponse(client.POST('/api/checkins', { body: checkin }));
	},
	getNotes: async (date?: string) => {
		return unwrapResponse(client.GET('/api/notes', dateQuery(date)));
	},
	createNote: async (note: NoteInput) => {
		return unwrapResponse(client.POST('/api/notes', { body: note }));
	},
	getExperiments: async () => {
		return unwrapResponse(client.GET('/api/experiments'));
	},
	getExperiment: async (experimentId: string) => {
		return unwrapResponse(client.GET('/api/experiments/{experiment_id}', {
			params: { path: { experiment_id: experimentId } }
		}));
	},
	getExperimentAnalysis: async (experimentId: string) => {
		return unwrapResponse(client.GET('/api/experiments/{experiment_id}/analysis', {
			params: { path: { experiment_id: experimentId } }
		}));
	},
	previewExperiment: async (experiment: ExperimentInput) => {
		return unwrapResponse(client.POST('/api/experiments/preview', { body: experiment }));
	},
	importExperiment: async (experiment: ExperimentInput) => {
		return unwrapResponse(client.POST('/api/experiments/import', { body: experiment }));
	},
	createExperiment: async (experiment: ExperimentInput) => {
		return unwrapResponse(client.POST('/api/experiments', { body: experiment }));
	},
	updateExperiment: async (experimentId: string, experiment: ExperimentInput) => {
		return unwrapResponse(client.PUT('/api/experiments/{experiment_id}', {
			params: { path: { experiment_id: experimentId } },
			body: experiment
		}));
	},
	refreshExperimentAnalyses: async () => {
		return unwrapResponse(client.POST('/api/experiments/refresh-analyses'));
	},
	getTargetMetrics: async () => {
		return unwrapResponse(client.GET('/api/target-metrics'));
	},
	getAssistantThreads: async () => {
		return unwrapResponse(client.GET('/api/assistant/threads'));
	},
	getAssistantArtifacts: async (params?: { kind?: string; status?: string }) => {
		return unwrapResponse(client.GET('/api/assistant/artifacts', {
			params: { query: params ?? {} }
		}));
	},
	createAssistantArtifact: async (artifact: AssistantArtifactInput) => {
		return unwrapResponse(client.POST('/api/assistant/artifacts', { body: artifact }));
	},
	activateAssistantArtifact: async (artifactId: string) => {
		return unwrapResponse(client.POST('/api/assistant/artifacts/{artifact_id}/activate', {
			params: { path: { artifact_id: artifactId } }
		}));
	},
	previewAssistantArtifactBundle: async (bundle: ArtifactBundleSpec) => {
		return unwrapResponse(client.POST('/api/assistant/artifact-bundles/preview', {
			body: bundle
		}));
	},
	importAssistantArtifactBundle: async (bundle: ArtifactBundleSpec) => {
		return unwrapResponse(client.POST('/api/assistant/artifact-bundles/import', {
			body: bundle
		}));
	},
	createAssistantThread: async (thread: AssistantThreadInput) => {
		return unwrapResponse(client.POST('/api/assistant/threads', { body: thread }));
	},
	getAssistantThreadMessages: async (threadId: string) => {
		return unwrapResponse(client.GET('/api/assistant/threads/{thread_id}/messages', {
			params: { path: { thread_id: threadId } }
		}));
	},
	getPrograms: async (status?: 'active' | 'retired') => {
		return unwrapResponse(client.GET('/api/programs', {
			params: { query: status ? { status } : {} }
		}));
	},
	getProgram: async (programId: string) => {
		return unwrapResponse(client.GET('/api/programs/{program_id}', {
			params: { path: { program_id: programId } }
		}));
	},
	importProgram: async (spec: Record<string, unknown>) => {
		return unwrapResponse(client.POST('/api/programs/import', { body: spec }));
	},
	retireProgram: async (programId: string) => {
		return unwrapResponse(client.PUT('/api/programs/{program_id}/retire', {
			params: { path: { program_id: programId } }
		}));
	},
	activateProgram: async (programId: string) => {
		return unwrapResponse(client.PUT('/api/programs/{program_id}/activate', {
			params: { path: { program_id: programId } }
		}));
	},
	getProgramVersions: async (programId: string) => {
		return unwrapResponse(client.GET('/api/programs/{program_id}/versions', {
			params: { path: { program_id: programId } }
		}));
	},
	importTraining: async (body: ImportRequest) => {
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
	}
};
