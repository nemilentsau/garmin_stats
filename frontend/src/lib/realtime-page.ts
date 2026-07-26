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

type LatestLoaderOptions<TArgs extends unknown[], TResult> = {
	onStart?: (...args: TArgs) => void;
	load: (...args: TArgs) => Promise<TResult>;
	onSuccess: (result: TResult, ...args: TArgs) => void;
	onError?: (error: unknown, ...args: TArgs) => void;
	onSettled?: (...args: TArgs) => void;
};

export function createLatestLoader<TArgs extends unknown[], TResult>(
	options: LatestLoaderOptions<TArgs, TResult>
): (...args: TArgs) => Promise<void> {
	const gate = createLatestRequestGate();
	return async (...args: TArgs) => {
		const request = gate.issue();
		options.onStart?.(...args);
		try {
			const result = await options.load(...args);
			if (gate.isCurrent(request)) options.onSuccess(result, ...args);
		} catch (error: unknown) {
			if (gate.isCurrent(request)) options.onError?.(error, ...args);
		} finally {
			if (gate.isCurrent(request)) options.onSettled?.(...args);
		}
	};
}

type RealtimeInitOptions = {
	fetchData: () => Promise<void>;
	setError: (message: string | null) => void;
	setLoading: (loading: boolean) => void;
};

export function startRealtimePage(options: RealtimeInitOptions): () => void {
	const gate = createLatestRequestGate();
	const refresh = async () => {
		const request = gate.issue();
		try {
			await options.fetchData();
			if (gate.isCurrent(request)) options.setError(null);
		} catch (error: unknown) {
			if (gate.isCurrent(request)) {
				options.setError(error instanceof Error ? error.message : String(error));
			}
			throw error;
		} finally {
			if (gate.isCurrent(request)) options.setLoading(false);
		}
	};

	refresh().catch(() => {});

	return createDataUpdateListener(refresh);
}

type DateLoaderOptions<T> = {
	setSelectedDate: (date: string) => void;
	clearData: () => void;
	fetchByDate: (date: string) => Promise<T>;
	setData: (data: T) => void;
	setError: (message: string | null) => void;
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
			options.setError(null);
		} catch (error: unknown) {
			if (currentRequest !== requestId) {
				return;
			}
			options.setError(error instanceof Error ? error.message : String(error));
		}
	};
}
