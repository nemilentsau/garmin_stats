/**
 * API client for Garmin Stats backend
 *
 * Type definitions are generated from the FastAPI OpenAPI spec.
 * To regenerate: bash scripts/generate-api-types.sh
 */

import createClient from 'openapi-fetch';
import type { components, paths } from './api-types';
import { API_BASE } from './config';

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
export type TodayCardLogUpdate = Schemas['TodayCardLogUpdateRequest'];
export type TodayResponse = Schemas['TodayResponse'];
export type Program = Schemas['Program'];
export type ProgramsResponse = Schemas['ProgramsResponse'];
export type ProgramVersion = Schemas['ProgramVersion'];
export type ProgramVersionsResponse = Schemas['ProgramVersionsResponse'];

function unwrap<T>(data: T | undefined, error: unknown): T {
	if (error) {
		throw new Error(typeof error === 'string' ? error : JSON.stringify(error));
	}
	if (data === undefined) {
		throw new Error('API response did not include JSON data');
	}
	return data;
}

const dateQuery = (date?: string) => ({ params: { query: date ? { date } : {} } });

export const api = {
	getDailyAggregates: async () => {
		const { data, error } = await client.GET('/api/daily-aggregates');
		return unwrap(data, error);
	},
	getDashboardOverview: async () => {
		const { data, error } = await client.GET('/api/dashboard');
		return unwrap(data, error);
	},
	getHeartRateDaily: async () => {
		const { data, error } = await client.GET('/api/heart-rate/daily');
		return unwrap(data, error);
	},
	getHrvDaily: async () => {
		const { data, error } = await client.GET('/api/hrv/daily');
		return unwrap(data, error);
	},
	getSleepDaily: async () => {
		const { data, error } = await client.GET('/api/sleep/daily');
		return unwrap(data, error);
	},
	getStressDaily: async () => {
		const { data, error } = await client.GET('/api/stress/daily');
		return unwrap(data, error);
	},
	getBodyBatteryDaily: async () => {
		const { data, error } = await client.GET('/api/body-battery/daily');
		return unwrap(data, error);
	},
	getRespirationDaily: async () => {
		const { data, error } = await client.GET('/api/respiration/daily');
		return unwrap(data, error);
	},
	getPulseOxDaily: async () => {
		const { data, error } = await client.GET('/api/pulse-ox/daily');
		return unwrap(data, error);
	},
	getSkinTempDaily: async () => {
		const { data, error } = await client.GET('/api/skin-temp/daily');
		return unwrap(data, error);
	},
	getHeartRateRaw: async (date?: string) => {
		const { data, error } = await client.GET('/api/heart-rate/raw', dateQuery(date));
		return unwrap(data, error);
	},
	getStressRaw: async (date?: string) => {
		const { data, error } = await client.GET('/api/stress/raw', dateQuery(date));
		return unwrap(data, error);
	},
	getBodyBatteryRaw: async (date?: string) => {
		const { data, error } = await client.GET('/api/body-battery/raw', dateQuery(date));
		return unwrap(data, error);
	},
	getPulseOxRaw: async (date?: string) => {
		const { data, error } = await client.GET('/api/pulse-ox/raw', dateQuery(date));
		return unwrap(data, error);
	},
	getRespirationRaw: async (date?: string) => {
		const { data, error } = await client.GET('/api/respiration/raw', dateQuery(date));
		return unwrap(data, error);
	},
	getSleepRaw: async (date?: string) => {
		const { data, error } = await client.GET('/api/sleep/raw', dateQuery(date));
		return unwrap(data, error);
	},
	getHrvRaw: async (date?: string) => {
		const { data, error } = await client.GET('/api/hrv/raw', dateQuery(date));
		return unwrap(data, error);
	},
	getSkinTempRaw: async (date?: string) => {
		const { data, error } = await client.GET('/api/skin-temp/raw', dateQuery(date));
		return unwrap(data, error);
	},
	getHrvInsights: async (date?: string) => {
		const { data, error } = await client.GET('/api/hrv/insights', dateQuery(date));
		return unwrap(data, error);
	},
	getHrvAnalysis: async () => {
		const { data, error } = await client.GET('/api/hrv/analysis');
		return unwrap(data, error);
	},
	getHeartRateInsights: async (date?: string) => {
		const { data, error } = await client.GET('/api/heart-rate/insights', dateQuery(date));
		return unwrap(data, error);
	},
	getHeartRateAnalysis: async () => {
		const { data, error } = await client.GET('/api/heart-rate/analysis');
		return unwrap(data, error);
	},
	getHRDistribution: async (date: string) => {
		const { data, error } = await client.GET('/api/heart-rate/distribution', {
			params: { query: { date } }
		});
		return unwrap(data, error);
	},
	triggerIngest: async () => {
		const { data, error } = await client.POST('/api/ingest');
		return unwrap(data, error);
	},
	triggerSync: async () => {
		const { data, error } = await client.POST('/api/ingest/sync');
		return unwrap(data, error);
	},
	getIngestStatus: async () => {
		const { data, error } = await client.GET('/api/ingest/status');
		return unwrap(data, error);
	},
	getSleepAnalysis: async () => {
		const { data, error } = await client.GET('/api/sleep/analysis');
		return unwrap(data, error);
	},
	getStressAnalysis: async () => {
		const { data, error } = await client.GET('/api/stress/analysis');
		return unwrap(data, error);
	},
	getBodyBatteryAnalysis: async () => {
		const { data, error } = await client.GET('/api/body-battery/analysis');
		return unwrap(data, error);
	},
	getProfile: async () => {
		const { data, error } = await client.GET('/api/profile');
		return unwrap(data, error);
	},
	updateProfile: async (profile: UserProfileInput) => {
		const { data, error } = await client.PUT('/api/profile', { body: profile });
		return unwrap(data, error);
	},
	getRoutines: async (status?: string) => {
		const { data, error } = await client.GET('/api/routines', {
			params: { query: status ? { status } : {} }
		});
		return unwrap(data, error);
	},
	getRoutineScheduleWindow: async (startDate: string) => {
		const { data, error } = await client.GET('/api/routines/schedule-window', {
			params: { query: { start_date: startDate } }
		});
		return unwrap(data, error);
	},
	getRoutineAssignments: async (routineId: string) => {
		const { data, error } = await client.GET('/api/routines/{routine_id}/assignments', {
			params: { path: { routine_id: routineId } }
		});
		return unwrap(data, error);
	},
	getCards: async (status?: string) => {
		const { data, error } = await client.GET('/api/cards', {
			params: { query: status ? { status } : {} }
		});
		return unwrap(data, error);
	},
	getToday: async (date: string) => {
		const { data, error } = await client.GET('/api/today', {
			params: { query: { date } }
		});
		return unwrap(data, error);
	},
	updateTodayCard: async (date: string, occurrenceKey: string, payload: TodayCardLogUpdate) => {
		const { data, error } = await client.PUT('/api/today/{date}/cards/{occurrence_key}', {
			params: { path: { date, occurrence_key: occurrenceKey } },
			body: payload
		});
		return unwrap(data, error);
	},
	getCardLogsRange: async (startDate: string, endDate: string) => {
		const { data, error } = await client.GET('/api/today/card-logs', {
			params: { query: { start_date: startDate, end_date: endDate } }
		});
		return unwrap(data, error);
	},
	getCheckins: async (date?: string) => {
		const { data, error } = await client.GET('/api/checkins', dateQuery(date));
		return unwrap(data, error);
	},
	createCheckin: async (checkin: DailyCheckInInput) => {
		const { data, error } = await client.POST('/api/checkins', { body: checkin });
		return unwrap(data, error);
	},
	getNotes: async (date?: string) => {
		const { data, error } = await client.GET('/api/notes', dateQuery(date));
		return unwrap(data, error);
	},
	createNote: async (note: NoteInput) => {
		const { data, error } = await client.POST('/api/notes', { body: note });
		return unwrap(data, error);
	},
	getExperiments: async () => {
		const { data, error } = await client.GET('/api/experiments');
		return unwrap(data, error);
	},
	getExperiment: async (experimentId: string) => {
		const { data, error } = await client.GET('/api/experiments/{experiment_id}', {
			params: { path: { experiment_id: experimentId } }
		});
		return unwrap(data, error);
	},
	getExperimentAnalysis: async (experimentId: string) => {
		const { data, error } = await client.GET('/api/experiments/{experiment_id}/analysis', {
			params: { path: { experiment_id: experimentId } }
		});
		return unwrap(data, error);
	},
	previewExperiment: async (experiment: ExperimentInput) => {
		const { data, error } = await client.POST('/api/experiments/preview', { body: experiment });
		return unwrap(data, error);
	},
	importExperiment: async (experiment: ExperimentInput) => {
		const { data, error } = await client.POST('/api/experiments/import', { body: experiment });
		return unwrap(data, error);
	},
	createExperiment: async (experiment: ExperimentInput) => {
		const { data, error } = await client.POST('/api/experiments', { body: experiment });
		return unwrap(data, error);
	},
	updateExperiment: async (experimentId: string, experiment: ExperimentInput) => {
		const { data, error } = await client.PUT('/api/experiments/{experiment_id}', {
			params: { path: { experiment_id: experimentId } },
			body: experiment
		});
		return unwrap(data, error);
	},
	refreshExperimentAnalyses: async () => {
		const { data, error } = await client.POST('/api/experiments/refresh-analyses');
		return unwrap(data, error);
	},
	getTargetMetrics: async () => {
		const { data, error } = await client.GET('/api/target-metrics');
		return unwrap(data, error);
	},
	getAssistantThreads: async () => {
		const { data, error } = await client.GET('/api/assistant/threads');
		return unwrap(data, error);
	},
	getAssistantArtifacts: async (params?: { kind?: string; status?: string }) => {
		const { data, error } = await client.GET('/api/assistant/artifacts', {
			params: { query: params ?? {} }
		});
		return unwrap(data, error);
	},
	createAssistantArtifact: async (artifact: AssistantArtifactInput) => {
		const { data, error } = await client.POST('/api/assistant/artifacts', { body: artifact });
		return unwrap(data, error);
	},
	activateAssistantArtifact: async (artifactId: string) => {
		const { data, error } = await client.POST('/api/assistant/artifacts/{artifact_id}/activate', {
			params: { path: { artifact_id: artifactId } }
		});
		return unwrap(data, error);
	},
	previewAssistantArtifactBundle: async (bundle: ArtifactBundleSpec) => {
		const { data, error } = await client.POST('/api/assistant/artifact-bundles/preview', {
			body: bundle
		});
		return unwrap(data, error);
	},
	importAssistantArtifactBundle: async (bundle: ArtifactBundleSpec) => {
		const { data, error } = await client.POST('/api/assistant/artifact-bundles/import', {
			body: bundle
		});
		return unwrap(data, error);
	},
	createAssistantThread: async (thread: AssistantThreadInput) => {
		const { data, error } = await client.POST('/api/assistant/threads', { body: thread });
		return unwrap(data, error);
	},
	getAssistantThreadMessages: async (threadId: string) => {
		const { data, error } = await client.GET('/api/assistant/threads/{thread_id}/messages', {
			params: { path: { thread_id: threadId } }
		});
		return unwrap(data, error);
	},
	getPrograms: async (status?: 'active' | 'retired') => {
		const { data, error } = await client.GET('/api/programs', {
			params: { query: status ? { status } : {} }
		});
		return unwrap(data, error);
	},
	getProgram: async (programId: string) => {
		const { data, error } = await client.GET('/api/programs/{program_id}', {
			params: { path: { program_id: programId } }
		});
		return unwrap(data, error);
	},
	importProgram: async (spec: Record<string, unknown>) => {
		const { data, error } = await client.POST('/api/programs/import', { body: spec });
		return unwrap(data, error);
	},
	retireProgram: async (programId: string) => {
		const { data, error } = await client.PUT('/api/programs/{program_id}/retire', {
			params: { path: { program_id: programId } }
		});
		return unwrap(data, error);
	},
	activateProgram: async (programId: string) => {
		const { data, error } = await client.PUT('/api/programs/{program_id}/activate', {
			params: { path: { program_id: programId } }
		});
		return unwrap(data, error);
	},
	getProgramVersions: async (programId: string) => {
		const { data, error } = await client.GET('/api/programs/{program_id}/versions', {
			params: { path: { program_id: programId } }
		});
		return unwrap(data, error);
	}
};
