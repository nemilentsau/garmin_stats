export type CardStatus = 'pending' | 'completed' | 'partial' | 'skipped';

type StatusCard = { occurrence_key: string; status: CardStatus };
type ChecklistAnswer = { item_id: string; checked: boolean; scale: number | null };
type ChecklistItemKind = 'checkbox' | 'tissue_check';

export function effectiveStatus(
	card: StatusCard,
	overrides: Record<string, string>
): CardStatus {
	return (overrides[card.occurrence_key] ?? card.status) as CardStatus;
}

export function toggledCompletionStatus(status: CardStatus): CardStatus {
	return status === 'completed' ? 'pending' : 'completed';
}

export function statusForVariant(option: string, status: CardStatus): CardStatus {
	return option === 'skip' ? 'skipped' : status;
}

export function deriveChecklistStatus(
	answers: ChecklistAnswer[],
	itemKinds: Record<string, ChecklistItemKind>
): CardStatus {
	if (answers.length === 0) return 'pending';
	const answered = answers.filter((answer) =>
		itemKinds[answer.item_id] === 'tissue_check' ? answer.scale !== null : answer.checked
	).length;
	if (answered === answers.length) return 'completed';
	return answered > 0 ? 'partial' : 'pending';
}
