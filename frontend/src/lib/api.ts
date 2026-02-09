/**
 * API client for Garmin Stats backend
 *
 * Type definitions are generated from the FastAPI OpenAPI spec.
 * To regenerate: bash scripts/generate-api-types.sh
 */

import type { components } from './api-types';

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

const API_BASE = 'http://localhost:8000';

async function fetchJson<T>(endpoint: string, init?: RequestInit): Promise<T> {
	const response = await fetch(`${API_BASE}${endpoint}`, init);
	if (!response.ok) {
		throw new Error(`API error: ${response.status} ${response.statusText}`);
	}
	return response.json();
}

export const api = {
	getDailyAggregates: () => fetchJson<DailyAggregates>('/api/daily-aggregates'),
	getWellness: (date?: string) =>
		fetchJson<WellnessData>(`/api/wellness${date ? `?date=${date}` : ''}`),
	getSleep: (date?: string) => fetchJson<SleepData>(`/api/sleep${date ? `?date=${date}` : ''}`),
	getHrv: (date?: string) => fetchJson<HrvData>(`/api/hrv${date ? `?date=${date}` : ''}`),
	getSkinTemp: (date?: string) =>
		fetchJson<SkinTempData>(`/api/skin-temp${date ? `?date=${date}` : ''}`),
	getDays: () => fetchJson<Schemas['DaysResponse']>('/api/days'),
	triggerIngest: () => fetchJson<IngestResult>('/api/ingest', { method: 'POST' }),
	getIngestStatus: () => fetchJson<IngestStatus>('/api/ingest/status')
};
