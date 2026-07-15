import assert from 'node:assert/strict';
import test from 'node:test';
import { createServer } from 'vite';

let server;
let recoveryFormat;

test.before(async () => {
	server = await createServer({
		configFile: 'vite.config.ts',
		optimizeDeps: { noDiscovery: true },
		server: { middlewareMode: true, hmr: false },
		appType: 'custom',
		logLevel: 'error'
	});
	recoveryFormat = await server.ssrLoadModule('/src/lib/recovery-format.ts');
});

test.after(async () => {
	await server?.close();
});

function sampleFlags() {
	return {
		oxygen: {
			kind: 'oxygen',
			status: 'normal',
			label: 'Oxygen',
			value: 96,
			threshold_low: 90.5,
			tab_href: '/pulse-ox'
		},
		thermoregulation: {
			kind: 'thermoregulation',
			status: 'normal',
			label: 'Skin temp',
			value: 0.1,
			threshold_low: -0.91,
			threshold_high: 0.83,
			tab_href: '/skin-temp'
		}
	};
}

function sampleFlagSeries() {
	return {
		oxygen: [
			{ date: '2026-04-29', status: 'low', value: 84, threshold_low: 90.5 },
			{ date: '2026-06-13', status: 'normal', value: 96, threshold_low: 90.5 }
		],
		thermoregulation: [
			{
				date: '2026-04-29',
				status: 'below_usual',
				value: -1.4,
				threshold_low: -0.91,
				threshold_high: 0.83
			},
			{
				date: '2026-06-13',
				status: 'normal',
				value: 0.1,
				threshold_low: -0.91,
				threshold_high: 0.83
			}
		]
	};
}

test('health flag strip labels the latest dashboard date, not calendar today', () => {
	const { healthFlagStripViewModel, flagDisplay } = recoveryFormat;

	const model = healthFlagStripViewModel({
		flags: sampleFlags(),
		flagSeries: sampleFlagSeries(),
		latestDate: '2026-06-13',
		hoveredDate: null
	});

	assert.equal(model.whenLabel, 'Jun 13');
	assert.deepEqual(model.flags.map((flag) => flagDisplay(flag).text), [
		'Oxygen: normal',
		'Skin temp: normal'
	]);
});

test('health flag strip renders selected historical date statuses', () => {
	const { healthFlagStripViewModel, flagDisplay } = recoveryFormat;

	const model = healthFlagStripViewModel({
		flags: sampleFlags(),
		flagSeries: sampleFlagSeries(),
		latestDate: '2026-06-13',
		hoveredDate: '2026-04-29'
	});

	assert.equal(model.whenLabel, 'Apr 29');
	assert.deepEqual(model.flags.map((flag) => flagDisplay(flag).text), [
		'Oxygen: low',
		'Skin temp: below usual'
	]);
	assert.deepEqual(
		model.flags.map((flag) => flag.value),
		[84, -1.4]
	);
});
