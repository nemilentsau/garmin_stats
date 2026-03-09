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

async function fetchJson<T>(endpoint: string, init?: RequestInit): Promise<T> {
	const response = await fetch(`${API_BASE}${endpoint}`, init);
	if (!response.ok) {
		throw new Error(`API error: ${response.status} ${response.statusText}`);
	}
	return response.json();
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
	getBodyBatteryAnalysis: () => fetchJson<BodyBatteryAnalysis>('/api/body-battery/analysis')
};
