import type { ScheduleOccurrence } from '$lib/api';
import { COLORS, DARK_MUTED_TEXT, withAlpha } from '$lib/colors';

export type SlotAccent = { color: string; shadow: string };
export type SlotName = ScheduleOccurrence['slot'];

export type CardPayload = ScheduleOccurrence['payload_json'];
type CardType = CardPayload['card_type'];
type Domain = 'strength' | 'breathwork' | 'meditation';

const CARD_TYPE_DOMAIN: Record<CardType, Domain | null> = {
	breath_timer: 'breathwork',
	meditation_timer: 'meditation',
	checklist: null
};

const DOMAIN_THEME: Record<Domain, { accent: string; icon: string }> = {
	strength: { accent: COLORS.skinTemp, icon: '🏋' },
	breathwork: { accent: COLORS.spo2, icon: '🫁' },
	meditation: { accent: COLORS.hrv, icon: '🧘' }
};

function domainOf(payload: CardPayload): Domain | null {
	if (payload.card_type === 'checklist') {
		// The backend allows any string here; only recognized domains map to a theme.
		const domain = payload.domain;
		return domain && domain in DOMAIN_THEME ? (domain as Domain) : null;
	}
	return CARD_TYPE_DOMAIN[payload.card_type];
}

/**
 * Returns the full domain theme (accent color, shadow, icon) for a card payload.
 * Falls back to a neutral accent for checklist cards with no domain.
 */
export function domainThemeOf(payload: CardPayload): { accent: string; shadow: string; icon: string } {
	const domain = domainOf(payload);
	if (domain) {
		const t = DOMAIN_THEME[domain];
		return { accent: t.accent, shadow: withAlpha(t.accent, '30'), icon: t.icon };
	}
	return { accent: DARK_MUTED_TEXT, shadow: withAlpha(DARK_MUTED_TEXT, '30'), icon: '' };
}

export const SLOT_ORDER: readonly SlotName[] = ['morning', 'midday', 'evening', 'anytime'];

export const SLOT_LABELS: Record<SlotName, string> = {
	morning: 'Morning',
	midday: 'Midday',
	evening: 'Evening',
	anytime: 'Anytime'
};

const SLOT_ACCENTS: Record<SlotName, SlotAccent> = {
	morning: { color: COLORS.respiration, shadow: withAlpha(COLORS.respiration, '30') },
	midday: { color: COLORS.spo2, shadow: withAlpha(COLORS.spo2, '30') },
	evening: { color: COLORS.hrv, shadow: withAlpha(COLORS.hrv, '30') },
	anytime: { color: COLORS.stress, shadow: withAlpha(COLORS.stress, '30') }
};

const DEFAULT_SLOT_ACCENT: SlotAccent = {
	color: DARK_MUTED_TEXT,
	shadow: withAlpha(DARK_MUTED_TEXT, '30')
};

export function slotAccent(slot: SlotName): SlotAccent {
	return SLOT_ACCENTS[slot] ?? DEFAULT_SLOT_ACCENT;
}

export function cardBrief(card: { payload_json: CardPayload }): string {
	const p = card.payload_json;
	switch (p.card_type) {
		case 'breath_timer':
		case 'meditation_timer':
			return p.duration_minutes ? `${p.duration_minutes} min` : '';
		case 'checklist':
			return p.items?.length ? `${p.items.length} items` : '';
	}
}
