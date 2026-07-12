/**
 * SSE client for real-time data updates from the backend.
 *
 * Listens for `data_updated` events and calls the provided callback.
 * EventSource auto-reconnects on connection loss (browser built-in).
 */

import { API_BASE } from './config';

export function createDataUpdateListener(onUpdate: () => void | Promise<void>): () => void {
	const source = new EventSource(`${API_BASE}/api/events`);

	source.addEventListener('data_updated', () => {
		console.debug('[SSE] data_updated received, refreshing data');
		try {
			const result = onUpdate();
			if (result instanceof Promise) {
				result.catch((e: unknown) => {
					console.warn('[SSE] refresh failed:', e instanceof Error ? e.message : e);
				});
			}
		} catch (e: unknown) {
			console.warn('[SSE] refresh failed:', e instanceof Error ? e.message : e);
		}
	});

	source.onerror = () => {
		if (source.readyState === EventSource.CONNECTING) {
			console.debug('[SSE] connection lost, reconnecting...');
		} else if (source.readyState === EventSource.CLOSED) {
			console.warn('[SSE] connection closed permanently');
		}
	};

	source.onopen = () => {
		console.debug('[SSE] connected');
	};

	return () => {
		source.close();
	};
}

export function createCoachUpdateListener(onUpdate: () => void | Promise<void>): () => void {
	const source = new EventSource(`${API_BASE}/api/events`);
	source.addEventListener('coach_updated', () => {
		try {
			Promise.resolve(onUpdate()).catch((e: unknown) => {
				console.warn('[SSE] coach refresh failed:', e instanceof Error ? e.message : e);
			});
		} catch (e: unknown) {
			console.warn('[SSE] coach refresh failed:', e instanceof Error ? e.message : e);
		}
	});
	return () => source.close();
}
