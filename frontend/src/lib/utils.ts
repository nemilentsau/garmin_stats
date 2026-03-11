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
