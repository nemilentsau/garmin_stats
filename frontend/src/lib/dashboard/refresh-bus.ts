/**
 * Dashboard refresh signal.
 *
 * A no-data pub/sub the overview shell uses to tell self-fetching axis sections
 * "the underlying data changed — re-fetch yourself" (on realtime SSE updates or a
 * manual Sync). The shell creates one bus and provides it via context; each axis
 * section subscribes its own reload. Nothing flows through this but the signal.
 */

export type RefreshBus = {
	/** Register a reload callback; returns an unsubscribe function. */
	subscribe: (cb: () => void) => () => void;
	/** Notify all current subscribers that data changed. */
	emit: () => void;
};

/** Context key under which the overview shell provides its {@link RefreshBus}. */
export const DASHBOARD_REFRESH = Symbol('dashboard-refresh');

export function createRefreshBus(): RefreshBus {
	const subscribers = new Set<() => void>();
	return {
		subscribe(cb) {
			subscribers.add(cb);
			return () => {
				subscribers.delete(cb);
			};
		},
		emit() {
			for (const cb of subscribers) cb();
		}
	};
}
