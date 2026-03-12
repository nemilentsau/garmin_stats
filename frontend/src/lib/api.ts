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
export type Routine = Schemas['Routine-Output'];
export type RoutineInput = Schemas['Routine-Input'];
export type RoutinesResponse = Schemas['RoutinesResponse'];
export type RoutineEntry = Schemas['RoutineEntry-Output'];
export type RoutineEntryInput = Schemas['RoutineEntry-Input'];
export type RoutineEntriesResponse = Schemas['RoutineEntriesResponse'];
export type DailyCheckIn = Schemas['DailyCheckIn-Output'];
export type DailyCheckInInput = Schemas['DailyCheckIn-Input'];
export type DailyCheckInsResponse = Schemas['DailyCheckInsResponse'];
export type Note = Schemas['Note-Output'];
export type NoteInput = Schemas['Note-Input'];
export type NotesResponse = Schemas['NotesResponse'];
export type Experiment = Schemas['Experiment-Output'];
export type ExperimentInput = Schemas['Experiment-Input'];
export type ExperimentsResponse = Schemas['ExperimentsResponse'];
export type TargetMetricDefinition = Schemas['TargetMetricDefinition'];
export type TargetMetricsResponse = Schemas['TargetMetricsResponse'];
export type AssistantThread = Schemas['AssistantThread'];
export type AssistantThreadInput = Schemas['AssistantThreadCreateRequest'];
export type AssistantThreadsResponse = Schemas['AssistantThreadsResponse'];
export type AssistantMessage = Schemas['AssistantMessage'];
export type AssistantMessageInput = Schemas['AssistantMessageCreateRequest'];
export type AssistantMessagesResponse = Schemas['AssistantMessagesResponse'];

async function fetchJson<T>(endpoint: string, init?: RequestInit): Promise<T> {
	const response = await fetch(`${API_BASE}${endpoint}`, init);
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
	getRoutines: () => fetchJson<RoutinesResponse>('/api/routines'),
	createRoutine: (routine: RoutineInput) => sendJson<Routine>('/api/routines', 'POST', routine),
	updateRoutine: (routineId: string, routine: RoutineInput) =>
		sendJson<Routine>(`/api/routines/${routineId}`, 'PUT', routine),
	getRoutineEntries: (routineId: string, date?: string) =>
		fetchJson<RoutineEntriesResponse>(
			`/api/routines/${routineId}/entries${date ? `?date=${date}` : ''}`
		),
	createRoutineEntry: (routineId: string, entry: RoutineEntryInput) =>
		sendJson<RoutineEntry>(`/api/routines/${routineId}/entries`, 'POST', entry),
	getCheckins: (date?: string) =>
		fetchJson<DailyCheckInsResponse>(`/api/checkins${date ? `?date=${date}` : ''}`),
	createCheckin: (checkin: DailyCheckInInput) =>
		sendJson<DailyCheckIn>('/api/checkins', 'POST', checkin),
	getNotes: (date?: string) => fetchJson<NotesResponse>(`/api/notes${date ? `?date=${date}` : ''}`),
	createNote: (note: NoteInput) => sendJson<Note>('/api/notes', 'POST', note),
	getExperiments: () => fetchJson<ExperimentsResponse>('/api/experiments'),
	getExperiment: (experimentId: string) => fetchJson<Experiment>(`/api/experiments/${experimentId}`),
	createExperiment: (experiment: ExperimentInput) =>
		sendJson<Experiment>('/api/experiments', 'POST', experiment),
	updateExperiment: (experimentId: string, experiment: ExperimentInput) =>
		sendJson<Experiment>(`/api/experiments/${experimentId}`, 'PUT', experiment),
	getTargetMetrics: () => fetchJson<TargetMetricsResponse>('/api/target-metrics'),
	getAssistantThreads: () => fetchJson<AssistantThreadsResponse>('/api/assistant/threads'),
	createAssistantThread: (thread: AssistantThreadInput) =>
		sendJson<AssistantThread>('/api/assistant/threads', 'POST', thread),
	getAssistantThreadMessages: (threadId: string) =>
		fetchJson<AssistantMessagesResponse>(`/api/assistant/threads/${threadId}/messages`)
};
