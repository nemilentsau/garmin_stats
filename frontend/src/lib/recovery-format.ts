/**
 * Display-only formatting for the recovery overview.
 *
 * Pure presentation: composes the state sentence, picks diverging colours for the
 * robust-z scale, and maps source-type / flag values to glyphs and labels. No
 * statistics — every value here comes already computed from the backend contract.
 */
import { COLORS, DARK_MUTED_TEXT } from './colors';
import type { DashboardOverview } from './api';

type RecoveryState = DashboardOverview['state'];
type OxygenHealthFlag = DashboardOverview['flags']['oxygen'];
type ThermoregulationHealthFlag = DashboardOverview['flags']['thermoregulation'];
type HealthFlag = OxygenHealthFlag | ThermoregulationHealthFlag;
type SourceType = DashboardOverview['evidence'][number]['source_type'];
type FlagTone = 'normal' | 'warning' | 'unknown';

const BAND_WORD: Record<string, string> = {
	suppressed: 'Suppressed recovery',
	typical: 'Typical recovery',
	strong: 'Strong recovery'
};

const TREND_WORD: Record<string, string> = {
	improving: 'improving',
	steady: 'holding steady',
	declining: 'declining'
};

/** "Typical recovery, improving" — the state-before-score sentence (Q4.1). */
export function stateSentence(state: RecoveryState): string {
	if (state.band == null) return 'Recovery score unavailable today';
	const band = BAND_WORD[state.band] ?? 'Recovery';
	if (state.trend == null) return band;
	return `${band}, ${TREND_WORD[state.trend] ?? state.trend}`;
}

/** Recovery good (green), poor (red), neutral (muted) on the z scale. */
const RECOVERY_GREEN = COLORS.heartRateResting;
const RECOVERY_RED = COLORS.heartRate;

/** Colour for a recovery-signed move: good helps recovery, bad hurts it. */
export function recoveryColor(good: boolean | null | undefined): string {
	if (good == null) return DARK_MUTED_TEXT;
	return good ? RECOVERY_GREEN : RECOVERY_RED;
}

/** Colour the score band tint (suppressed = red, strong = green, typical = neutral). */
export function bandColor(band: string | null | undefined): string {
	if (band === 'suppressed') return RECOVERY_RED;
	if (band === 'strong') return RECOVERY_GREEN;
	return DARK_MUTED_TEXT;
}

/** Short source-type glyph + tooltip: native / device / derived. */
export function sourceGlyph(source: SourceType): { glyph: string; title: string } {
	switch (source) {
		case 'native':
			return { glyph: 'nat', title: 'Source-native measurement' };
		case 'device':
			return { glyph: 'dev', title: 'Device-computed from native readings' };
		default:
			return { glyph: 'der', title: 'Garmin-derived composite' };
	}
}

/** Direction arrow for a raw delta (up / down / flat). */
export function deltaArrow(deltaZ: number | null | undefined): string {
	if (deltaZ == null || Math.abs(deltaZ) < 0.05) return '·';
	return deltaZ > 0 ? '▲' : '▼';
}

/** A health exception's human label + tone for the strip. */
export function flagDisplay(flag: HealthFlag): { text: string; tone: FlagTone } {
	if (flag.status === 'unknown') {
		return { text: `${flag.label}: no reading`, tone: 'unknown' };
	}

	if (flag.kind === 'oxygen') {
		if (flag.status === 'low') {
			return { text: `${flag.label}: low`, tone: 'warning' };
		}
		return { text: `${flag.label}: normal`, tone: 'normal' };
	}

	if (flag.status === 'below_usual') {
		return { text: `${flag.label}: below usual`, tone: 'warning' };
	}
	if (flag.status === 'above_usual') {
		return { text: `${flag.label}: above usual`, tone: 'warning' };
	}
	return { text: `${flag.label}: normal`, tone: 'normal' };
}

/** Colour for a health exception tone. */
export function flagColor(tone: FlagTone): string {
	if (tone === 'warning') return COLORS.stress;
	if (tone === 'unknown') return DARK_MUTED_TEXT;
	return COLORS.heartRateResting;
}
