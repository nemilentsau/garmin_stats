import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

const skinTempPage = readFileSync(
	new URL('../src/routes/skin-temp/+page.svelte', import.meta.url),
	'utf8'
);
const bodyBatteryPage = readFileSync(
	new URL('../src/routes/body-battery/+page.svelte', import.meta.url),
	'utf8'
);

test('skin-temperature UI consumes only explicit Fahrenheit response fields', () => {
	assert.match(skinTempPage, /deviation_f/);
	assert.match(skinTempPage, /deviation_7_day_f/);
	assert.match(skinTempPage, /avg_nightly_f/);
	assert.match(skinTempPage, /°F|&deg;F/);
	assert.doesNotMatch(skinTempPage, /°C|&deg;C/);
});

test('Body Battery is presented as a unitless 0–100 score', () => {
	assert.match(bodyBatteryPage, /Body Battery \(0–100\)/);
	assert.doesNotMatch(bodyBatteryPage, /battery %/);
	assert.doesNotMatch(bodyBatteryPage, /unit="%"/);
});
