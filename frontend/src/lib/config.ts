import { env } from '$env/dynamic/public';

function normalizeBaseUrl(baseUrl: string): string {
	return baseUrl.endsWith('/') ? baseUrl.slice(0, -1) : baseUrl;
}

export const API_BASE = normalizeBaseUrl(env.PUBLIC_API_BASE_URL || 'http://localhost:8000');
