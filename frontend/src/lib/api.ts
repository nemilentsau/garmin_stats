/**
 * API client for Garmin Stats backend
 *
 * Type definitions are generated from the FastAPI OpenAPI spec.
 * To regenerate: bash scripts/generate-api-types.sh
 */

import type { components } from './api-types';
import { API_BASE } from './config';

type Schemas = components['schemas'];

// Re-export generated types with existing frontend names
export type WellnessData = Schemas['WellnessResponse'];
export type SleepData = Schemas['SleepResponse'];
export type HrvData = Schemas['HrvResponse'];
export type SkinTempData = Schemas['SkinTempResponse'];
export type DailyAggregates = Schemas['DailyAggregatesResponse'];
export type DailyMetric = Schemas['DailyMetric'];
export type IngestResult = Schemas['IngestResult'];
export type IngestStatus = Schemas['IngestStatus'];
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

async function fetchJson<T>(endpoint: string, init?: RequestInit): Promise<T> {
	const response = await fetch(`${API_BASE}${endpoint}`, {
		cache: 'no-store',
		...init
	});
	if (!response.ok) {
		throw new Error(`API error: ${response.status} ${response.statusText}`);
	}
	return response.json();
}

async function sendJson<T>(endpoint: string, method: 'POST' | 'PUT', body: unknown): Promise<T> {
	return fetchJson<T>(endpoint, {
		method,
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify(body)
	});
}

export const api = {
	getDailyAggregates: () => fetchJson<DailyAggregates>('/api/daily-aggregates'),
	getDashboardOverview: () => fetchJson<DashboardOverview>('/api/dashboard'),
	getWellness: (date?: string) =>
		fetchJson<WellnessData>(`/api/wellness${date ? `?date=${date}` : ''}`),
	getSleep: (date?: string) => fetchJson<SleepData>(`/api/sleep${date ? `?date=${date}` : ''}`),
	getHrv: (date?: string) => fetchJson<HrvData>(`/api/hrv${date ? `?date=${date}` : ''}`),
	getHrvInsights: (date?: string) =>
		fetchJson<HrvInsights>(`/api/hrv/insights${date ? `?date=${date}` : ''}`),
	getHrvAnalysis: () => fetchJson<HrvAnalysis>('/api/hrv/analysis'),
	getSkinTemp: (date?: string) =>
		fetchJson<SkinTempData>(`/api/skin-temp${date ? `?date=${date}` : ''}`),
	getHeartRateInsights: (date?: string) =>
		fetchJson<HeartRateInsights>(`/api/heart-rate/insights${date ? `?date=${date}` : ''}`),
	getHeartRateAnalysis: () => fetchJson<HRAnalysis>('/api/heart-rate/analysis'),
	getHRDistribution: (date: string) =>
		fetchJson<HRDistribution>(`/api/heart-rate/distribution?date=${date}`),
	getDays: () => fetchJson<Schemas['DaysResponse']>('/api/days'),
	triggerIngest: () => fetchJson<IngestResult>('/api/ingest', { method: 'POST' }),
	getIngestStatus: () => fetchJson<IngestStatus>('/api/ingest/status'),
	getSleepAnalysis: () => fetchJson<SleepAnalysis>('/api/sleep/analysis'),
	getStressAnalysis: () => fetchJson<StressAnalysis>('/api/stress/analysis'),
	getBodyBatteryAnalysis: () => fetchJson<BodyBatteryAnalysis>('/api/body-battery/analysis'),
	getProfile: () => fetchJson<UserProfile>('/api/profile'),
	updateProfile: (profile: UserProfileInput) => sendJson<UserProfile>('/api/profile', 'PUT', profile),
	getRoutines: (status?: string) =>
		fetchJson<RoutineSchedulesResponse>(`/api/routines${status ? `?status=${status}` : ''}`),
	getRoutineScheduleWindow: (startDate: string) =>
		fetchJson<ScheduleWindow>(
			`/api/routines/schedule-window?start_date=${encodeURIComponent(startDate)}`
		),
	getRoutineAssignments: (routineId: string) =>
		fetchJson<RoutineAssignmentsResponse>(`/api/routines/${routineId}/assignments`),
	getCards: (status?: string) =>
		fetchJson<CardTemplatesResponse>(`/api/cards${status ? `?status=${status}` : ''}`),
	getToday: (date: string) => fetchJson<TodayResponse>(`/api/today?date=${date}`),
	updateTodayCard: (date: string, occurrenceKey: string, payload: TodayCardLogUpdate) =>
		sendJson<CardLog>(`/api/today/${date}/cards/${encodeURIComponent(occurrenceKey)}`, 'PUT', payload),
	getCardLogsRange: (startDate: string, endDate: string) =>
		fetchJson<CardLogRangeResponse>(`/api/today/card-logs?start_date=${encodeURIComponent(startDate)}&end_date=${encodeURIComponent(endDate)}`),
	getCheckins: (date?: string) =>
		fetchJson<DailyCheckInsResponse>(`/api/checkins${date ? `?date=${date}` : ''}`),
	createCheckin: (checkin: DailyCheckInInput) =>
		sendJson<DailyCheckIn>('/api/checkins', 'POST', checkin),
	getNotes: (date?: string) => fetchJson<NotesResponse>(`/api/notes${date ? `?date=${date}` : ''}`),
	createNote: (note: NoteInput) => sendJson<Note>('/api/notes', 'POST', note),
	getExperiments: () => fetchJson<ExperimentsResponse>('/api/experiments'),
	getExperiment: (experimentId: string) =>
		fetchJson<ExperimentWithAnalysis>(`/api/experiments/${experimentId}`),
	getExperimentAnalysis: (experimentId: string) =>
		fetchJson<ExperimentAnalysis | null>(`/api/experiments/${experimentId}/analysis`),
	previewExperiment: (experiment: ExperimentInput) =>
		sendJson<ExperimentPreviewResponse>('/api/experiments/preview', 'POST', experiment),
	importExperiment: (experiment: ExperimentInput) =>
		sendJson<ExperimentWithAnalysis>('/api/experiments/import', 'POST', experiment),
	createExperiment: (experiment: ExperimentInput) =>
		sendJson<Experiment>('/api/experiments', 'POST', experiment),
	updateExperiment: (experimentId: string, experiment: ExperimentInput) =>
		sendJson<Experiment>(`/api/experiments/${experimentId}`, 'PUT', experiment),
	refreshExperimentAnalyses: () =>
		sendJson<{ refreshed: number }>('/api/experiments/refresh-analyses', 'POST', {}),
	getTargetMetrics: () => fetchJson<TargetMetricsResponse>('/api/target-metrics'),
	getAssistantThreads: () => fetchJson<AssistantThreadsResponse>('/api/assistant/threads'),
	getAssistantArtifacts: (params?: { kind?: string; status?: string }) =>
		fetchJson<AssistantArtifactsResponse>(
			`/api/assistant/artifacts${
				params?.kind || params?.status
					? `?${[
							params?.kind ? `kind=${encodeURIComponent(params.kind)}` : '',
							params?.status ? `status=${encodeURIComponent(params.status)}` : ''
						]
							.filter(Boolean)
							.join('&')}`
					: ''
			}`
		),
	createAssistantArtifact: (artifact: AssistantArtifactInput) =>
		sendJson<AssistantArtifact>('/api/assistant/artifacts', 'POST', artifact),
	activateAssistantArtifact: (artifactId: string) =>
		sendJson<AssistantArtifact>(`/api/assistant/artifacts/${artifactId}/activate`, 'POST', {}),
	previewAssistantArtifactBundle: (bundle: ArtifactBundleSpec) =>
		sendJson<ArtifactBundlePreviewResponse>('/api/assistant/artifact-bundles/preview', 'POST', bundle),
	importAssistantArtifactBundle: (bundle: ArtifactBundleSpec) =>
		sendJson<ArtifactBundleImportResponse>('/api/assistant/artifact-bundles/import', 'POST', bundle),
	createAssistantThread: (thread: AssistantThreadInput) =>
		sendJson<AssistantThread>('/api/assistant/threads', 'POST', thread),
	getAssistantThreadMessages: (threadId: string) =>
		fetchJson<AssistantMessagesResponse>(`/api/assistant/threads/${threadId}/messages`),
	getPrograms: (status?: string) =>
		fetchJson<ProgramsResponse>(`/api/programs${status ? `?status=${status}` : ''}`),
	getProgram: (programId: string) => fetchJson<Program>(`/api/programs/${programId}`),
	importProgram: (spec: Record<string, unknown>) =>
		sendJson<Program>('/api/programs/import', 'POST', spec),
	retireProgram: (programId: string) =>
		sendJson<Program>(`/api/programs/${programId}/retire`, 'PUT', {}),
	activateProgram: (programId: string) =>
		sendJson<Program>(`/api/programs/${programId}/activate`, 'PUT', {}),
	getProgramVersions: (programId: string) =>
		fetchJson<ProgramVersionsResponse>(`/api/programs/${programId}/versions`)
};
