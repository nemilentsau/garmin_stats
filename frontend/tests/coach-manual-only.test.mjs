import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

test('viewing a completed review is read-only until the user sends a message', () => {
	const page = readFileSync('src/routes/coach/+page.svelte', 'utf8');
	const api = readFileSync('src/lib/api.ts', 'utf8');

	assert.equal(api.includes('getCoachReviewThread:'), true);
	assert.match(page, /api\.getCoachReviewThread\(review\.id\)/);
	assert.match(page, /reviewThread\?\.review_id === selectedReviewId && reviewThread\.status === 'open'/);
	assert.match(page, /await api\.openCoachReviewThread\(selectedReviewId\)/);
	assert.equal(page.includes("activeReview.status === 'complete' && reviewThread"), false);
});

test('review history exposes every field in prior immutable snapshots', () => {
	const page = readFileSync('src/routes/coach/+page.svelte', 'utf8');

	assert.match(page, /renderMarkdown\(revision\.content_md\)/);
	assert.match(page, /revision\.outcome\.replaceAll\('_', ' '\)/);
	assert.match(page, /revision\.confidence/);
	assert.match(page, /revision\.snapshot_complete/);
	assert.match(page, /revision\.refs/);
	assert.match(page, /revision\.follow_up_questions/);
	assert.match(page, /revision\.plot_observations/);
	assert.match(page, /revision\.history_used/);
	assert.match(page, /revision\.measurement_assessment/);
});

test('coach refreshes and general-thread messages reject stale responses', () => {
	const page = readFileSync('src/routes/coach/+page.svelte', 'utf8');

	assert.match(page, /const refreshAllGate = createLatestRequestGate\(\)/);
	assert.match(page, /const threadMessagesGate = createLatestRequestGate\(\)/);
	assert.match(page, /threadMessagesGate\.isCurrent\(request\)/);
	assert.match(page, /activeThreadId !== threadId/);
	assert.match(page, /refreshAllGate\.isCurrent\(request\)/);
});
