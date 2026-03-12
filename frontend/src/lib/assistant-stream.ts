import { API_BASE } from './config';
import type { AssistantMessage, AssistantMessageInput } from './api';

export type AssistantStreamEvent =
	| { type: 'delta'; text: string }
	| {
			type: 'done';
			message: AssistantMessage;
			session_id: string | null;
			snapshot_id: string;
			run_id: string;
	  }
	| { type: 'error'; message: string; run_id: string };

function parseLine(line: string): AssistantStreamEvent {
	return JSON.parse(line) as AssistantStreamEvent;
}

export async function streamAssistantReply(
	threadId: string,
	message: AssistantMessageInput,
	onEvent: (event: AssistantStreamEvent) => void | Promise<void>
): Promise<void> {
	const response = await fetch(`${API_BASE}/api/assistant/threads/${threadId}/messages`, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify(message)
	});

	if (!response.ok) {
		throw new Error(`API error: ${response.status} ${response.statusText}`);
	}
	if (!response.body) {
		throw new Error('Assistant stream unavailable');
	}

	const reader = response.body.getReader();
	const decoder = new TextDecoder();
	let buffer = '';

	while (true) {
		const { done, value } = await reader.read();
		buffer += decoder.decode(value ?? new Uint8Array(), { stream: !done });

		const lines = buffer.split('\n');
		buffer = lines.pop() ?? '';

		for (const line of lines) {
			const trimmed = line.trim();
			if (!trimmed) {
				continue;
			}
			await onEvent(parseLine(trimmed));
		}

		if (done) {
			if (buffer.trim()) {
				await onEvent(parseLine(buffer.trim()));
			}
			return;
		}
	}
}
