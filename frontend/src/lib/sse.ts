/**
 * SSE client for real-time data updates from the backend.
 *
 * Listens for `data_updated` events and calls the provided callback.
 * EventSource auto-reconnects on connection loss (browser built-in).
 */

const API_BASE = 'http://localhost:8000';

export function createDataUpdateListener(onUpdate: () => void): () => void {
	const source = new EventSource(`${API_BASE}/api/events`);

	source.addEventListener('data_updated', () => {
		onUpdate();
	});

	return () => {
		source.close();
	};
}
