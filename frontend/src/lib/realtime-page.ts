import { createDataUpdateListener } from './sse';

export type LatestRequestGate = {
	issue: () => number;
	invalidate: () => void;
	isCurrent: (request: number) => boolean;
};

export function createLatestRequestGate(): LatestRequestGate {
	let latestRequest = 0;
	return {
		issue: () => ++latestRequest,
		invalidate: () => { latestRequest += 1; },
		isCurrent: (request) => request === latestRequest
	};
}

type RealtimeInitOptions = {
	fetchData: () => Promise<void>;
	setError: (message: string) => void;
	setLoading: (loading: boolean) => void;
};

export function startRealtimePage(options: RealtimeInitOptions): () => void {
	options
		.fetchData()
		.catch((error: unknown) => {
			options.setError(error instanceof Error ? error.message : String(error));
		})
		.finally(() => {
			options.setLoading(false);
		});

	return createDataUpdateListener(options.fetchData);
}

type DateLoaderOptions<T> = {
	setSelectedDate: (date: string) => void;
	clearData: () => void;
	fetchByDate: (date: string) => Promise<T>;
	setData: (data: T) => void;
	setError: (message: string) => void;
};

export function createDateLoader<T>(options: DateLoaderOptions<T>): (date: string) => Promise<void> {
	let requestId = 0;

	return async (date: string) => {
		options.setSelectedDate(date);
		options.clearData();
		const currentRequest = ++requestId;

		if (!date) {
			return;
		}

		try {
			const data = await options.fetchByDate(date);
			if (currentRequest !== requestId) {
				return;
			}
			options.setData(data);
		} catch (error: unknown) {
			if (currentRequest !== requestId) {
				return;
			}
			options.setError(error instanceof Error ? error.message : String(error));
		}
	};
}
