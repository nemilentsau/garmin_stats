export type CardStatus = 'pending' | 'completed' | 'partial' | 'skipped';

type StatusCard = { occurrence_key: string; status: CardStatus };

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

type StatusPersistTask = {
	key: string;
	attempted: CardStatus;
	initialConfirmed: CardStatus;
	persist: () => Promise<boolean>;
	isCurrent: () => boolean;
	rollback: (confirmed: CardStatus) => void;
};

export function createStatusPersistQueue() {
	const queues = new Map<string, Promise<void>>();
	const confirmedStatuses = new Map<string, CardStatus>();

	return {
		enqueue(task: StatusPersistTask): Promise<void> {
			if (!confirmedStatuses.has(task.key)) {
				confirmedStatuses.set(task.key, task.initialConfirmed);
			}

			const previous = queues.get(task.key) ?? Promise.resolve();
			const current = previous.then(async () => {
				const saved = await task.persist();
				if (saved) {
					confirmedStatuses.set(task.key, task.attempted);
				} else if (task.isCurrent()) {
					task.rollback(confirmedStatuses.get(task.key) ?? task.initialConfirmed);
				}
			});
			queues.set(task.key, current);
			void current.then(() => {
				if (queues.get(task.key) === current) {
					queues.delete(task.key);
					confirmedStatuses.delete(task.key);
				}
			});
			return current;
		}
	};
}
