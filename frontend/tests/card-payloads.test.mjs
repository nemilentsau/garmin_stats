import assert from 'node:assert/strict';
import test from 'node:test';
import { createServer } from 'vite';

// Behavioral unit tests for card-payloads helpers loaded through Vite so TS modules
// and $lib aliases resolve without a separate build step.

let server;
let mod;

test.before(async () => {
	server = await createServer({
		configFile: 'vite.config.ts',
		server: { middlewareMode: true },
		appType: 'custom',
		logLevel: 'error'
	});
	mod = await server.ssrLoadModule('/src/lib/routines/card-payloads.ts');
});

test.after(async () => {
	await server?.close();
});

test('cardBrief summarizes a breath timer by duration', () => {
	const { cardBrief } = mod;
	assert.equal(cardBrief({ payload_json: { card_type: 'breath_timer', duration_minutes: 5 } }), '5 min');
});

test('cardBrief counts strength exercises', () => {
	const { cardBrief } = mod;
	assert.equal(
		cardBrief({ payload_json: { card_type: 'strength_session', exercises: [{}, {}] } }),
		'2 exercises'
	);
});

test('cardBrief summarizes a checklist as N items', () => {
	const { cardBrief } = mod;
	assert.equal(
		cardBrief({ payload_json: { card_type: 'checklist', items: [{}, {}, {}] } }),
		'3 items'
	);
});

test('domainOf maps card_type to a domain key', () => {
	const { domainOf } = mod;
	assert.equal(domainOf({ card_type: 'running_workout' }), 'running');
	assert.equal(domainOf({ card_type: 'checklist', domain: 'strength' }), 'strength');
});

test('domainOf returns null for a checklist with no domain', () => {
	const { domainOf } = mod;
	assert.equal(domainOf({ card_type: 'checklist', domain: null }), null);
	assert.equal(domainOf({ card_type: 'checklist' }), null);
});
