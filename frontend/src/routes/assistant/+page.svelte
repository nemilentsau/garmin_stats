<script lang="ts">
	import { onMount, tick } from 'svelte';

	import { api, type AssistantMessage, type AssistantThread, type AssistantThreadInput } from '$lib/api';
	import { streamAssistantReply, type AssistantStreamEvent } from '$lib/assistant-stream';
	import { COLORS, withAlpha } from '$lib/colors';
	import { renderMarkdown } from '$lib/markdown';
	import { errorMessage, makeId } from '$lib/utils';

	const quickPrompts = [
		{
			label: 'Daily briefing',
			prompt:
				'Give me a concise daily recovery briefing. Focus on sleep, HRV, resting heart rate, and any obvious caution flags.'
		},
		{
			label: 'Weekly review',
			prompt:
				'Review the recent week and tell me what patterns stand out, what confounders matter, and what I should adjust next.'
		},
		{
			label: 'Experiment scan',
			prompt:
				'Look at my active routines and experiments. Tell me what seems worth continuing, what looks noisy, and what needs cleaner tracking.'
		}
	];

	const modelOptions = [
		{ value: 'haiku', label: 'Haiku' },
		{ value: 'sonnet', label: 'Sonnet' },
		{ value: 'opus', label: 'Opus' }
	];

	let loading = $state(true);
	let sending = $state(false);
	let error: string | null = $state(null);

	let threads: AssistantThread[] = $state([]);
	let messages: AssistantMessage[] = $state([]);
	let selectedThreadId = $state('');
	let composer = $state('');
	let newThreadTitle = $state('Recovery coach');
	let newThreadModel = $state('sonnet');
	let streamEl: HTMLDivElement | undefined = $state();

	async function scrollToBottom() {
		await tick();
		if (streamEl) {
			streamEl.scrollTop = streamEl.scrollHeight;
		}
	}

	let activeThread = $derived.by(
		() => threads.find((thread) => thread.id === selectedThreadId) ?? null
	);
	let threadCount = $derived.by(() => threads.length);
	let conversationCount = $derived.by(() => threads.filter((thread) => thread.last_message_at).length);

	async function loadThreads() {
		const response = await api.getAssistantThreads();
		threads = response.threads;
		if (!selectedThreadId && threads.length > 0) {
			selectedThreadId = threads[0].id;
		}
	}

	async function loadMessages(threadId: string) {
		const response = await api.getAssistantThreadMessages(threadId);
		messages = response.messages;
		void scrollToBottom();
	}

	async function ensureThread(): Promise<AssistantThread> {
		if (activeThread) {
			return activeThread;
		}

		const payload: AssistantThreadInput = {
			id: makeId('thread'),
			title: newThreadTitle.trim() || 'Recovery coach',
			mode: 'general',
			model: newThreadModel
		};
		const thread = await api.createAssistantThread(payload);
		threads = [thread, ...threads];
		selectedThreadId = thread.id;
		messages = [];
		return thread;
	}

	async function createThread() {
		error = null;
		try {
			const payload: AssistantThreadInput = {
				id: makeId('thread'),
				title: newThreadTitle.trim() || 'Recovery coach',
				mode: 'general',
				model: newThreadModel
			};
			const thread = await api.createAssistantThread(payload);
			threads = [thread, ...threads];
			selectedThreadId = thread.id;
			messages = [];
			newThreadTitle = 'Recovery coach';
		} catch (e: unknown) {
			error = errorMessage(e);
		}
	}

	function selectThread(threadId: string) {
		selectedThreadId = threadId;
	}

	$effect(() => {
		if (!selectedThreadId || loading || sending) {
			return;
		}

		void loadMessages(selectedThreadId).catch((e: unknown) => {
			error = errorMessage(e);
		});
	});

	onMount(() => {
		void loadThreads()
			.catch((e: unknown) => {
				error = errorMessage(e);
			})
			.finally(() => {
				loading = false;
			});
	});

	function threadSubtitle(thread: AssistantThread): string {
		if (thread.last_message_at) {
			return new Date(thread.last_message_at).toLocaleString();
		}
		return 'No conversation yet';
	}

	async function handleStreamEvent(
		event: AssistantStreamEvent,
		placeholderId: string,
		threadId: string
	) {
		if (event.type === 'delta') {
			messages = messages.map((message) =>
				message.id === placeholderId
					? { ...message, content_markdown: message.content_markdown + event.text }
					: message
			);
			void scrollToBottom();
			return;
		}

		if (event.type === 'done') {
			messages = messages.map((message) => (message.id === placeholderId ? event.message : message));
			await loadThreads();
			selectedThreadId = threadId;
			void scrollToBottom();
			return;
		}

		messages = messages.filter((message) => message.id !== placeholderId);
		throw new Error(event.message);
	}

	async function sendPrompt(content: string) {
		const trimmed = content.trim();
		if (!trimmed || sending) {
			return;
		}

		sending = true;
		error = null;
		let optimisticMessageIds: string[] = [];
		let streamStarted = false;
		try {
			const thread = await ensureThread();
			const userMessage: AssistantMessage = {
				id: makeId('message'),
				thread_id: thread.id,
				role: 'user',
				content_markdown: trimmed,
				structured_payload_json: {},
				evidence_refs_json: [],
				created_at: new Date().toISOString()
			};
			const placeholderId = makeId('assistant');
			const placeholder: AssistantMessage = {
				id: placeholderId,
				thread_id: thread.id,
				role: 'assistant',
				content_markdown: '',
				structured_payload_json: {},
					evidence_refs_json: [],
					created_at: new Date().toISOString()
				};
				messages = [...messages, userMessage, placeholder];
				optimisticMessageIds = [userMessage.id, placeholderId];
				composer = '';
				void scrollToBottom();

				await streamAssistantReply(
					thread.id,
					{
						id: userMessage.id,
						content: trimmed
					},
					(event) => {
						streamStarted = true;
						return handleStreamEvent(event, placeholderId, thread.id);
					}
				);
			} catch (e: unknown) {
				if (!streamStarted && optimisticMessageIds.length > 0) {
					const optimisticIds = new Set(optimisticMessageIds);
					messages = messages.filter((message) => !optimisticIds.has(message.id));
				}
				error = errorMessage(e);
			} finally {
				sending = false;
			}
		}

	function handleComposerKeydown(event: KeyboardEvent) {
		if (event.key === 'Enter' && !event.shiftKey) {
			event.preventDefault();
			void submitComposer();
		}
	}

	async function submitComposer() {
		await sendPrompt(composer);
	}
</script>

{#if loading}
	<section class="loading-shell">
		<div class="loading-card">Loading assistant workspace...</div>
	</section>
{:else}
	<section
		class="assistant-shell"
		style={`--assistant-gradient-a: ${COLORS.respiration}; --assistant-gradient-b: ${COLORS.spo2}; --thread-badge-bg: ${withAlpha(COLORS.hrv, '1f')};`}
	>
		<div class="summary-row">
			<div class="summary-stat">
				<span>Threads</span>
				<strong>{threadCount}</strong>
			</div>
			<div class="summary-stat">
				<span>Active convos</span>
				<strong>{conversationCount}</strong>
			</div>
			<div class="summary-stat accent">
				<span>Runtime</span>
				<strong>Claude</strong>
			</div>
		</div>

		{#if error}
			<div class="error-banner">{error}</div>
		{/if}

		<div class="assistant-grid">
			<aside class="threads-panel">
				<div class="panel-head">
					<p>Threads</p>
					<h2>Conversation lanes</h2>
				</div>

				<div class="new-thread-card">
					<label>
						<span>Thread title</span>
						<input bind:value={newThreadTitle} placeholder="Recovery coach" />
					</label>
					<label>
						<span>Model</span>
						<select bind:value={newThreadModel}>
							{#each modelOptions as option}
								<option value={option.value}>{option.label}</option>
							{/each}
						</select>
					</label>
					<button class="create-button" onclick={createThread}>Create thread</button>
				</div>

				<div class="thread-list">
					{#each threads as thread}
						<button
							class:selected={thread.id === selectedThreadId}
							class="thread-card"
							onclick={() => selectThread(thread.id)}
						>
							<div class="thread-topline">
								<strong>{thread.title}</strong>
								<span>{thread.model}</span>
							</div>
							<p>{threadSubtitle(thread)}</p>
						</button>
					{/each}
					{#if threads.length === 0}
						<div class="empty-state">Create the first thread to start asking for recovery guidance.</div>
					{/if}
				</div>
			</aside>

			<section class="chat-panel">
				<div class="panel-head">
					<p>Assistant</p>
					<h2>{activeThread ? activeThread.title : 'No thread selected'}</h2>
				</div>

				<div class="quick-actions">
					{#each quickPrompts as action}
						<button class="quick-chip" onclick={() => sendPrompt(action.prompt)} disabled={sending}>
							{action.label}
						</button>
					{/each}
				</div>

				<div class="message-stream" bind:this={streamEl}>
					{#if messages.length === 0}
						<div class="empty-conversation">
							<p>Ask for a briefing, compare a routine to recovery, or request a plan draft.</p>
							<span>
								Examples: "Did my sleep and HRV move together this week?" or "What should I change if
								I want better recovery for lifting tomorrow?"
							</span>
						</div>
					{/if}

					{#each messages as message}
						<article class:assistant={message.role === 'assistant'} class:user={message.role === 'user'} class="message-card">
							<div class="message-meta">
								<strong>{message.role === 'assistant' ? 'Assistant' : 'You'}</strong>
								<span>{message.created_at ? new Date(message.created_at).toLocaleTimeString() : 'now'}</span>
							</div>
							<div class="message-body">
								{#if message.content_markdown}
									{@html renderMarkdown(message.content_markdown)}
								{:else}
									<p class="thinking">Thinking...</p>
								{/if}
							</div>
						</article>
					{/each}
				</div>

				<form
					class="composer"
					onsubmit={(event) => {
						event.preventDefault();
						void submitComposer();
					}}
				>
					<textarea
						bind:value={composer}
						rows="4"
						placeholder="Ask about recovery, routine impact, or what experiment to run next..."
						disabled={sending}
						onkeydown={handleComposerKeydown}
					></textarea>
					<div class="composer-actions">
						<p>Enter to send · Shift+Enter for newline</p>
						<button type="submit" disabled={sending || !composer.trim()}>
							{sending ? 'Streaming...' : 'Send'}
						</button>
					</div>
				</form>
			</section>
		</div>
	</section>
{/if}

<style>
	.assistant-shell {
		display: grid;
		gap: 24px;
	}

	.loading-shell {
		display: grid;
		place-items: center;
		min-height: 60vh;
	}

	.loading-card,
	.error-banner,
	.threads-panel,
	.chat-panel {
		border: 1px solid rgba(255, 255, 255, 0.08);
		background:
			linear-gradient(160deg, rgba(255, 255, 255, 0.02), rgba(255, 255, 255, 0.01)),
			radial-gradient(circle at top right, rgba(91, 181, 166, 0.12), transparent 34%);
		box-shadow: 0 22px 60px rgba(0, 0, 0, 0.28);
	}

	.loading-card,
	.error-banner {
		padding: 20px 24px;
		border-radius: 22px;
	}

	.error-banner {
		color: #ffd4cb;
		background:
			linear-gradient(160deg, rgba(232, 93, 74, 0.18), rgba(255, 255, 255, 0.02)),
			radial-gradient(circle at top right, rgba(232, 93, 74, 0.15), transparent 30%);
	}

	.summary-row {
		display: grid;
		grid-template-columns: repeat(3, minmax(0, 1fr));
		gap: 14px;
	}

	.summary-stat {
		padding: 16px 18px;
		border-radius: 14px;
		border: 1px solid rgba(255, 255, 255, 0.08);
		background: rgba(255, 255, 255, 0.03);
	}

	.summary-stat.accent {
		background: linear-gradient(160deg, rgba(91, 181, 166, 0.12), rgba(74, 144, 217, 0.06));
	}

	.summary-stat span {
		display: block;
		margin-bottom: 8px;
		font-family: 'DM Mono', monospace;
		font-size: 11px;
		letter-spacing: 0.08em;
		text-transform: uppercase;
		color: #8da0af;
	}

	.summary-stat strong {
		display: block;
		font-size: 1.15rem;
		color: #edf3f7;
	}

	.panel-head p,
	.composer-actions p,
	.message-meta span,
	.thread-card p,
	.empty-state,
	.empty-conversation span {
		font-family: 'DM Mono', monospace;
		font-size: 11px;
		letter-spacing: 0.08em;
		text-transform: uppercase;
		color: #7e93a4;
	}

	h2 {
		margin: 0;
		color: #edf3f7;
		font-size: 1.35rem;
	}

	.assistant-grid {
		display: grid;
		grid-template-columns: minmax(280px, 360px) minmax(0, 1fr);
		gap: 20px;
		align-items: start;
	}

	.threads-panel,
	.chat-panel {
		border-radius: 26px;
		padding: 22px;
	}

	.panel-head {
		margin-bottom: 18px;
	}

	.panel-head p {
		margin: 0 0 6px;
	}

	.new-thread-card {
		display: grid;
		gap: 12px;
		padding: 16px;
		border-radius: 20px;
		background: rgba(255, 255, 255, 0.03);
		border: 1px solid rgba(255, 255, 255, 0.06);
	}

	label {
		display: grid;
		gap: 6px;
	}

	label span {
		font-size: 12px;
		color: #c4d1da;
	}

	input,
	select,
	textarea {
		width: 100%;
		border-radius: 14px;
		border: 1px solid rgba(255, 255, 255, 0.08);
		background: rgba(9, 14, 20, 0.72);
		color: #edf3f7;
		padding: 12px 14px;
		font: inherit;
	}

	.create-button,
	.quick-chip,
	.thread-card,
	.composer button {
		border: none;
		font: inherit;
		cursor: pointer;
	}

	.create-button,
	.composer button {
		background: linear-gradient(135deg, var(--assistant-gradient-a), var(--assistant-gradient-b));
		color: #08111a;
		font-weight: 700;
		padding: 12px 16px;
		border-radius: 999px;
	}

	.thread-list {
		display: grid;
		gap: 10px;
		margin-top: 16px;
	}

	.thread-card {
		text-align: left;
		padding: 14px 16px;
		border-radius: 18px;
		background: rgba(255, 255, 255, 0.02);
		border: 1px solid rgba(255, 255, 255, 0.05);
		color: #edf3f7;
		transition: transform 0.18s ease, border-color 0.18s ease, background 0.18s ease;
	}

	.thread-card:hover,
	.thread-card.selected {
		transform: translateY(-1px);
		border-color: rgba(91, 181, 166, 0.5);
		background: linear-gradient(160deg, rgba(91, 181, 166, 0.11), rgba(255, 255, 255, 0.02));
	}

	.thread-topline {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 12px;
	}

	.thread-topline span {
		padding: 4px 8px;
		border-radius: 999px;
		background: var(--thread-badge-bg);
		color: #ddd3f5;
		font-family: 'DM Mono', monospace;
		font-size: 11px;
		text-transform: uppercase;
	}

	.quick-actions {
		display: flex;
		flex-wrap: wrap;
		gap: 10px;
		margin-bottom: 16px;
	}

	.quick-chip {
		padding: 10px 14px;
		border-radius: 999px;
		background: rgba(255, 255, 255, 0.04);
		color: #c7d3dd;
		border: 1px solid rgba(255, 255, 255, 0.06);
	}

	.quick-chip:hover {
		background: rgba(255, 255, 255, 0.08);
	}

	.message-stream {
		display: grid;
		gap: 12px;
		min-height: 420px;
		max-height: 62vh;
		overflow: auto;
		padding-right: 4px;
	}

	.message-card {
		padding: 16px 18px;
		border-radius: 22px;
		border: 1px solid rgba(255, 255, 255, 0.06);
		background: rgba(255, 255, 255, 0.03);
		max-width: 88%;
	}

	.message-card.user {
		margin-left: auto;
		background: linear-gradient(160deg, rgba(74, 144, 217, 0.16), rgba(255, 255, 255, 0.02));
	}

	.message-card.assistant {
		background:
			linear-gradient(160deg, rgba(91, 181, 166, 0.13), rgba(255, 255, 255, 0.02)),
			radial-gradient(circle at top right, rgba(155, 107, 205, 0.12), transparent 36%);
	}

	.message-meta {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 12px;
		margin-bottom: 10px;
	}

	.message-body {
		color: #d7e2ea;
		line-height: 1.6;
	}

	.message-body :global(p) {
		margin: 0 0 0.6em;
	}

	.message-body :global(p:last-child) {
		margin-bottom: 0;
	}

	.message-body :global(h1),
	.message-body :global(h2),
	.message-body :global(h3) {
		margin: 0.8em 0 0.4em;
		color: #edf3f7;
	}

	.message-body :global(h1) {
		font-size: 1.2rem;
	}

	.message-body :global(h2) {
		font-size: 1.1rem;
	}

	.message-body :global(h3) {
		font-size: 1rem;
	}

	.message-body :global(ul),
	.message-body :global(ol) {
		margin: 0 0 0.6em;
		padding-left: 1.4em;
	}

	.message-body :global(li) {
		margin-bottom: 0.25em;
	}

	.message-body :global(code) {
		padding: 0.15em 0.4em;
		border-radius: 6px;
		background: rgba(255, 255, 255, 0.06);
		font-family: 'DM Mono', monospace;
		font-size: 0.9em;
	}

	.message-body :global(pre) {
		margin: 0.6em 0;
		padding: 12px 14px;
		border-radius: 12px;
		background: rgba(0, 0, 0, 0.3);
		overflow-x: auto;
	}

	.message-body :global(pre code) {
		padding: 0;
		background: none;
	}

	.message-body :global(strong) {
		color: #edf3f7;
	}

	.message-body :global(blockquote) {
		margin: 0.6em 0;
		padding-left: 12px;
		border-left: 3px solid rgba(91, 181, 166, 0.5);
		color: #a8bac7;
	}

	.message-body :global(hr) {
		border: none;
		border-top: 1px solid rgba(255, 255, 255, 0.08);
		margin: 0.8em 0;
	}

	.message-body :global(a) {
		color: #5bb5a6;
		text-decoration: underline;
		text-underline-offset: 2px;
	}

	.thinking {
		color: #7e93a4;
		font-style: italic;
		margin: 0;
	}

	.empty-conversation,
	.empty-state {
		padding: 18px;
		border-radius: 18px;
		background: rgba(255, 255, 255, 0.02);
		border: 1px dashed rgba(255, 255, 255, 0.08);
		color: #b8c7d0;
	}

	.empty-conversation p {
		margin: 0 0 8px;
		font-size: 1rem;
		color: #edf3f7;
	}

	.composer {
		display: grid;
		gap: 12px;
		margin-top: 18px;
	}

	.composer textarea {
		min-height: 112px;
		resize: vertical;
	}

	.composer-actions {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 16px;
	}

	.composer button:disabled,
	.quick-chip:disabled {
		opacity: 0.6;
		cursor: default;
	}

	@media (max-width: 1100px) {
		.summary-row,
		.assistant-grid {
			grid-template-columns: 1fr;
		}

	}

	@media (max-width: 720px) {
		.threads-panel,
		.chat-panel {
			padding: 18px;
		}

		.summary-row {
			grid-template-columns: 1fr;
		}

		.message-card {
			max-width: 100%;
		}

		.composer-actions {
			flex-direction: column;
			align-items: stretch;
		}
	}
</style>
