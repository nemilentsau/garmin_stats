/** Async-coordination helpers for the HRV tab's snapshot loads. */

export type HistoricalApplyOptions = {
	/** Apply the snapshot's selected-night sub-fetch to the detail panel. */
	applyHistorical: boolean;
	/** Clear any stale night-detail error (nothing open, or the open night matches). */
	clearDetailError: boolean;
};

/**
 * Decide how a completed snapshot load should apply its selected-night sub-fetch.
 *
 * `captured` is the night the load was keyed to when it STARTED; `selectedDate` is the night
 * currently selected when it finishes. Apply the night detail only if that night is still the
 * selected one (the user didn't move to another night meanwhile), so a snapshot's historical
 * sub-fetch can never clobber a fresher night selection. This is the single source of that
 * predicate, shared by the SSE/initial load and the baseline-window switch so the two can't drift.
 */
export function historicalApplyOptions(
	captured: string,
	selectedDate: string
): HistoricalApplyOptions {
	return {
		applyHistorical: captured !== '' && captured === selectedDate,
		clearDetailError: captured === '' || captured === selectedDate
	};
}
