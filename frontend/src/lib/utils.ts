/**
 * Shared frontend utilities.
 */

/** Generate a prefixed unique ID for client-created entities. */
export function makeId(prefix: string): string {
	return `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

/** Extract a human-readable message from an unknown thrown value. */
export function errorMessage(e: unknown): string {
	return e instanceof Error ? e.message : String(e);
}

/** Narrow an unknown value to a plain string-keyed record. */
export function isRecord(value: unknown): value is Record<string, unknown> {
	return typeof value === 'object' && value !== null && !Array.isArray(value);
}
