<script lang="ts">
	import { onDestroy, onMount } from 'svelte';
	import { replaceState } from '$app/navigation';
	import { page } from '$app/state';
	import {
		api,
		type CoachBriefResponse,
		type CoachJournalResponse,
		type CoachMessage,
		type CoachReview,
		type CoachReviewRevision,
		type CoachStatus,
		type CoachThread,
		type JournalEntry
	} from '$lib/api';
	import { measurementLabel, sessionLabel } from '$lib/coach/verdict';
	import { renderMarkdown } from '$lib/markdown';
	import { createLatestRequestGate, startRealtimePage } from '$lib/realtime-page';
	import { createCoachUpdateListener } from '$lib/sse';
	import { errorMessage } from '$lib/utils';

	type Tab = 'reviews' | 'conversation';

	let status: CoachStatus | null = $state(null);
	let reviews: CoachReview[] = $state([]);
	let threads: CoachThread[] = $state([]);
	let messages: CoachMessage[] = $state([]);
	let reviewMessages: CoachMessage[] = $state([]);
	let reviewRevisions: CoachReviewRevision[] = $state([]);
	let brief: CoachBriefResponse | null = $state(null);
	let journal: CoachJournalResponse | null = $state(null);
	let activeThreadId: string | null = $state(null);
	let activeReviewId: string | null = $state(null);
	let loading = $state(true);
	let error: string | null = $state(null);
	let draft = $state('');
	let reviewDraft = $state('');
	let reviewThread: CoachThread | null = $state(null);
	let newThreadTitle = $state('');
	let busy = $state(false);
	let failedPlots = $state<Set<string>>(new Set());
	let questionAnswers = $state<Record<number, string>>({});
	let tab: Tab = $state(
		page.url.searchParams.get('review')
			? 'reviews'
			: page.url.searchParams.get('tab') === 'conversation'
				? 'conversation'
				: 'reviews'
	);

	// One-shot deep-link consumption (`/runs/[id]` links here as `/coach?review=<id>`):
	// captured once from the URL at component init, NOT re-read from `page.url` on every
	// refresh. `refreshAll` runs on every SSE tick and after every send/create/close action;
	// re-reading the query param each time would keep snapping the selection back to the
	// deep-linked review even after the user picked a different one. Cleared (and the param
	// stripped from the URL) once the deep-linked review is found in the reviews list, or
	// as soon as the user makes an explicit selection via `chooseReview`.
	let pendingDeepLinkReviewId: string | null = page.url.searchParams.get('review');

	let activeThread = $derived(threads.find((thread) => thread.id === activeThreadId) ?? null);
	let activeReview = $derived(
		reviews.find((review) => review.id === activeReviewId) ?? reviews[0] ?? null
	);
	let hasAnyAnswer = $derived(
		Object.values(questionAnswers).some((answer) => answer.trim().length > 0)
	);
	let awaitingCoach = $derived(messages.length > 0 && messages[messages.length - 1]?.role === 'user');
	let awaitingReviewCoach = $derived(
		reviewMessages.length > 0 && reviewMessages[reviewMessages.length - 1]?.role === 'user'
	);
	let messagePane: HTMLDivElement | null = $state(null);
	let reviewMessagePane: HTMLDivElement | null = $state(null);
	const reviewConversationGate = createLatestRequestGate();
	const threadMessagesGate = createLatestRequestGate();
	const refreshAllGate = createLatestRequestGate();

	$effect(() => {
		void messages;
		if (messagePane) messagePane.scrollTop = messagePane.scrollHeight;
	});
	$effect(() => {
		void reviewMessages;
		if (reviewMessagePane) reviewMessagePane.scrollTop = reviewMessagePane.scrollHeight;
	});
	let workerLine = $derived.by(() => {
		if (!status) return '';
		if (!status.worker_enabled) return 'Coach worker is paused';
		if (status.running_job) return `Running ${status.running_job.kind.replaceAll('_', ' ')}`;
		return `Worker active · ${status.queued_count} queued`;
	});

	function selectTab(next: Tab): void {
		tab = next;
		// `page.url` is stale after a prior `replaceState` (SvelteKit 2.69 never reassigns it),
		// so read the live address bar via `location` instead.
		const params = new URLSearchParams(new URL(location.href).searchParams);
		params.set('tab', next);
		if (next === 'conversation') params.delete('review');
		replaceState(`?${params.toString()}`, {});
	}

	function clearReviewParam(): void {
		// See note in `selectTab`: `page.url` can be stale after `replaceState`, so this reads
		// the live URL from `location` rather than trusting `page.url`.
		const currentUrl = new URL(location.href);
		if (!currentUrl.searchParams.has('review')) return;
		const params = new URLSearchParams(currentUrl.searchParams);
		params.delete('review');
		const query = params.toString();
		replaceState(query ? `?${query}` : currentUrl.pathname, {});
	}

	function reviewOutcome(review: CoachReview): string {
		// Real outcomes use the shared plain-language vocabulary; legacy rows that only have
		// the old `verdict` field fall back to the raw enum text.
		const outcome = review.outcome
			? sessionLabel(review.outcome)
			: (review.verdict?.replaceAll('_', ' ') ?? 'not assessed');
		return review.outcome && (review.status === 'queued' || review.status === 'generating')
			? `previous: ${outcome}`
			: outcome;
	}

	function reviewKindLabel(kind: CoachReview['kind']): string {
		if (kind === 'day') return 'Day debrief';
		if (kind === 'week') return 'Weekly synthesis';
		return 'Run review';
	}

	function journalEntryTakeaway(entry: JournalEntry): string {
		const firstLine = entry.content_md.split('\n').find((line) => line.trim().length > 0) ?? '';
		return entry.run_summary?.takeaway ?? firstLine;
	}

	function markPlotUnavailable(plotName: string): void {
		failedPlots = new Set(failedPlots).add(plotName);
	}

	async function refreshMessages(threadId: string | null): Promise<void> {
		const request = threadMessagesGate.issue();
		try {
			const nextMessages = threadId ? (await api.getCoachMessages(threadId)).messages : [];
			if (!threadMessagesGate.isCurrent(request) || activeThreadId !== threadId) return;
			messages = nextMessages;
		} catch (cause: unknown) {
			if (!threadMessagesGate.isCurrent(request) || activeThreadId !== threadId) return;
			throw cause;
		}
	}

	async function refreshReviewConversation(review: CoachReview | null): Promise<void> {
		const request = reviewConversationGate.issue();
		if (!review || review.status !== 'complete') {
			reviewThread = null;
			reviewMessages = [];
			reviewRevisions = [];
			return;
		}
		if (reviewThread?.review_id !== review.id) {
			reviewThread = null;
			reviewMessages = [];
			reviewRevisions = [];
		}
		let nextThread: CoachThread | null;
		let nextRevisions: { revisions: CoachReviewRevision[] };
		let nextMessages: { messages: CoachMessage[] };
		try {
			[nextThread, nextRevisions] = await Promise.all([
				api.getCoachReviewThread(review.id),
				api.getCoachReviewRevisions(review.id)
			]);
			nextMessages = nextThread ? await api.getCoachMessages(nextThread.id) : { messages: [] };
		} catch (cause: unknown) {
			if (!reviewConversationGate.isCurrent(request) || activeReviewId !== review.id) return;
			throw cause;
		}
		if (!reviewConversationGate.isCurrent(request) || activeReviewId !== review.id) return;
		reviewThread = nextThread;
		reviewMessages = nextMessages.messages;
		reviewRevisions = nextRevisions.revisions;
	}

	async function refreshAll(): Promise<void> {
		const request = refreshAllGate.issue();
		let nextStatus: CoachStatus;
		let nextReviews: { reviews: CoachReview[] };
		let nextThreads: { threads: CoachThread[] };
		let nextBrief: CoachBriefResponse;
		let nextJournal: CoachJournalResponse;
		try {
			[nextStatus, nextReviews, nextThreads, nextBrief, nextJournal] = await Promise.all([
				api.getCoachStatus(),
				api.getCoachReviews({ limit: 100 }),
				api.getCoachThreads(),
				api.getCoachBrief(),
				api.getCoachJournal()
			]);
		} catch (cause: unknown) {
			if (!refreshAllGate.isCurrent(request)) return;
			throw cause;
		}
		if (!refreshAllGate.isCurrent(request)) return;
		status = nextStatus;
		reviews = nextReviews.reviews;
		threads = nextThreads.threads;
		brief = nextBrief;
		journal = nextJournal;
		// Fresh review data just arrived — let any previously-404'd evidence plot retry
		// (the worker may have generated it since). Reassigning (not mutating) the Set is
		// required for the `{#if failedPlots.has(...)}` reads below to pick up the change.
		failedPlots = new Set();
		if (pendingDeepLinkReviewId && reviews.some((review) => review.id === pendingDeepLinkReviewId)) {
			activeReviewId = pendingDeepLinkReviewId;
			pendingDeepLinkReviewId = null;
			clearReviewParam();
		} else if (!activeReviewId && reviews[0]) {
			activeReviewId = reviews[0].id;
		}
		if (!activeThreadId || !threads.some((thread) => thread.id === activeThreadId)) {
			activeThreadId = threads[0]?.id ?? null;
		}
		await Promise.all([
			refreshMessages(activeThreadId),
			refreshReviewConversation(activeReview)
		]);
		if (refreshAllGate.isCurrent(request)) error = null;
	}

	async function chooseReview(review: CoachReview): Promise<void> {
		activeReviewId = review.id;
		pendingDeepLinkReviewId = null;
		clearReviewParam();
		failedPlots = new Set();
		try {
			await refreshReviewConversation(review);
		} catch (e: unknown) {
			error = errorMessage(e);
		}
	}

	async function chooseThread(threadId: string): Promise<void> {
		activeThreadId = threadId;
		try {
			await refreshMessages(threadId);
		} catch (e: unknown) {
			error = errorMessage(e);
		}
	}

	async function createThread(): Promise<void> {
		const title = newThreadTitle.trim();
		if (!title || busy) return;
		busy = true;
		try {
			const thread = await api.createCoachThread(title);
			newThreadTitle = '';
			await refreshAll();
			await chooseThread(thread.id);
		} catch (e: unknown) {
			error = errorMessage(e);
		} finally {
			busy = false;
		}
	}

	async function sendMessage(): Promise<void> {
		const content = draft.trim();
		if (!content || !activeThreadId || busy) return;
		busy = true;
		try {
			await api.sendCoachMessage(activeThreadId, content);
			draft = '';
			await refreshAll();
		} catch (e: unknown) {
			error = errorMessage(e);
		} finally {
			busy = false;
		}
	}

	async function sendReviewMessage(): Promise<void> {
		const content = reviewDraft.trim();
		if (!content || busy) return;
		const selectedReviewId = activeReview?.id;
		if (!selectedReviewId) return;
		const revisionRequested = content.toLowerCase().startsWith('update the review:');
		busy = true;
		try {
			const thread =
				reviewThread?.review_id === selectedReviewId && reviewThread.status === 'open'
					? reviewThread
					: await api.openCoachReviewThread(selectedReviewId);
			reviewThread = thread;
			await api.sendCoachMessage(thread.id, content, revisionRequested);
			reviewDraft = '';
			await refreshAll();
		} catch (e: unknown) {
			error = errorMessage(e);
		} finally {
			busy = false;
		}
	}

	async function sendAnswers(review: CoachReview): Promise<void> {
		const lines = review.follow_up_questions
			.map((q, i) => ({ q, a: (questionAnswers[i] ?? '').trim() }))
			.filter(({ a }) => a.length > 0)
			.map(({ q, a }) => `- Q: ${q}\n  A: ${a}`);
		if (lines.length === 0 || busy) return;
		busy = true;
		try {
			const thread =
				reviewThread?.review_id === review.id && reviewThread.status === 'open'
					? reviewThread
					: await api.openCoachReviewThread(review.id);
			reviewThread = thread;
			await api.sendCoachMessage(
				thread.id,
				`Update the review: here are my answers to your questions.\n${lines.join('\n')}`,
				true
			);
			questionAnswers = {};
			await refreshAll();
		} catch (e: unknown) {
			error = errorMessage(e);
		} finally {
			busy = false;
		}
	}

	async function retryReview(reviewId: string): Promise<void> {
		busy = true;
		try {
			await api.retryCoachReview(reviewId);
			await refreshAll();
		} catch (e: unknown) {
			error = errorMessage(e);
		} finally {
			busy = false;
		}
	}

	async function closeThread(): Promise<void> {
		if (!activeThreadId) return;
		busy = true;
		try {
			await api.closeCoachThread(activeThreadId);
			await refreshAll();
		} catch (e: unknown) {
			error = errorMessage(e);
		} finally {
			busy = false;
		}
	}

	async function retryClose(): Promise<void> {
		if (!activeThreadId) return;
		busy = true;
		try {
			await api.retryCoachThreadClose(activeThreadId);
			await refreshAll();
		} catch (e: unknown) {
			error = errorMessage(e);
		} finally {
			busy = false;
		}
	}

	let closeDataListener: (() => void) | undefined;
	let closeCoachListener: (() => void) | undefined;
	onMount(() => {
		closeDataListener = startRealtimePage({
			fetchData: refreshAll,
			setError: (message) => (error = message),
			setLoading: (value) => (loading = value)
		});
		closeCoachListener = createCoachUpdateListener(refreshAll);
	});
	onDestroy(() => {
		closeDataListener?.();
		closeCoachListener?.();
	});
</script>

<svelte:head><title>Coach - Garmin Stats</title></svelte:head>

<div class="coach-page">
	<header class="page-heading">
		<div class="heading-left">
			<h1>Coach</h1>
			<div class="tab-switch" role="tablist" aria-label="Coach workspace view">
				<button
					role="tab"
					aria-selected={tab === 'reviews'}
					class:active={tab === 'reviews'}
					onclick={() => selectTab('reviews')}
				>Reviews</button>
				<button
					role="tab"
					aria-selected={tab === 'conversation'}
					class:active={tab === 'conversation'}
					onclick={() => selectTab('conversation')}
				>Conversation</button>
			</div>
		</div>
		{#if workerLine}<span class="worker-line">{workerLine}</span>{/if}
	</header>

	{#if error}<p class="error-line" role="alert">{error}</p>{/if}
	{#if loading}
		<p class="loading-line">Loading coach workspace…</p>
	{:else if tab === 'reviews'}
		{#if journal && journal.watch_items.length > 0}
			<div class="watch-strip" aria-label="What the coach is watching">
				<span class="watch-label">Watching</span>
				{#each journal.watch_items as item (item.source_id + item.text)}
					<span class="watch-item">{item.text}</span>
				{/each}
			</div>
		{/if}
		<div class="workspace">
			<aside class="rail" aria-label="Review history">
				<h2>Review history</h2>
				<div class="rail-scroll">
					{#each reviews as review (review.id)}
						<button
							class="rail-row review-row"
							class:active={review.id === activeReview?.id}
							onclick={() => chooseReview(review)}
						>
							<span class="row-top">
								<span class="tabular">{review.date}</span>
								<span class="row-status">{review.status.replaceAll('_', ' ')}</span>
							</span>
							<span class="row-sub">{reviewKindLabel(review.kind)} · {reviewOutcome(review)}</span>
						</button>
					{:else}
						<p class="empty-line">No review history.</p>
					{/each}
				</div>
				<details class="brief">
					<summary>Coach brief</summary>
					{#if brief?.brief}
						<div class="markdown-body brief-body">{@html renderMarkdown(brief.brief.content_md)}</div>
					{:else}
						<p class="empty-line">
							The coach writes this durable memory itself after a successful review or a
							closed conversation. It stays empty until the first review succeeds.
						</p>
					{/if}
				</details>
				<details class="brief journal">
					<summary>Journal</summary>
					{#if journal && journal.entries.length > 0}
						<ul class="journal-list">
							{#each journal.entries as entry (entry.id)}
								<li>
									<details class="journal-entry">
										<summary>
											<span class="tabular">{entry.ts.slice(0, 10)}</span>
											<span class="journal-takeaway">{journalEntryTakeaway(entry)}</span>
										</summary>
										<div class="markdown-body journal-body">{@html renderMarkdown(entry.content_md)}</div>
									</details>
								</li>
							{/each}
						</ul>
					{:else}
						<p class="empty-line">No journal yet.</p>
					{/if}
				</details>
			</aside>

			<section class="pane" aria-labelledby="review-pane-heading">
				{#if activeReview}
					<div class="pane-head">
						<div>
							<h2 id="review-pane-heading" class="pane-title">
								{reviewKindLabel(activeReview.kind)}
								<span class="tabular pane-date">{activeReview.date}</span>
							</h2>
							{#if activeReview.headline}
								<p class="pane-headline">{activeReview.headline}</p>
							{/if}
							<p class="pane-meta">
								{activeReview.status.replaceAll('_', ' ')} · {reviewOutcome(activeReview)}
								{#if activeReview.measurement_assessment}
									· {measurementLabel(activeReview.measurement_assessment.status)}
								{/if}
							</p>
						</div>
						{#if activeReview.status === 'failed'}
							<button class="btn" onclick={() => retryReview(activeReview.id)} disabled={busy}>Retry review</button>
						{/if}
					</div>
					<div class="pane-scroll">
						{#if activeReview.content_md}
							<div class="markdown-body">{@html renderMarkdown(activeReview.content_md)}</div>
						{:else if activeReview.status === 'failed'}
							<p class="error-line failure-reason" role="alert">
								{activeReview.error ?? 'This review failed before producing a response.'}
							</p>
						{:else}
							<p class="empty-line">This review is {activeReview.status.replaceAll('_', ' ')}. Its evidence-backed response will appear here.</p>
						{/if}
						{#if activeReview.refs.length > 0}
							<p class="refs">Evidence: {activeReview.refs.map((ref) => `${ref.kind}:${ref.value}`).join(' · ')}</p>
						{/if}
						{#if activeReview.plot_observations.length > 0}
							<section class="plot-evidence" aria-labelledby="plot-evidence-heading">
								<h3 id="plot-evidence-heading">Plot evidence used</h3>
								<div class="plot-list">
									{#each activeReview.plot_observations as observation (`${observation.plot}:${observation.observation}`)}
										<figure>
											{#if failedPlots.has(observation.plot)}
												<div class="plot-unavailable">Evidence image unavailable. The persisted observation remains below.</div>
											{:else}
												<img
													src={api.coachPlotUrl(observation.plot)}
													alt="Coach evidence plot for this observation"
													onerror={() => markPlotUnavailable(observation.plot)}
												/>
											{/if}
											<figcaption>
												<span>{observation.observation}</span>
												<code>{observation.plot}</code>
											</figcaption>
										</figure>
									{/each}
								</div>
							</section>
						{/if}
						{#if activeReview.follow_up_questions.length > 0}
							<section class="coach-questions" aria-labelledby="coach-questions-heading">
								<h3 id="coach-questions-heading">Coach questions</h3>
								{#each activeReview.follow_up_questions as question, index (index)}
									<div class="question-row">
										<p class="question-text">{question}</p>
										{#if activeReview.status === 'complete'}
											<input
												class="question-answer"
												placeholder="Your answer…"
												bind:value={questionAnswers[index]}
											/>
										{/if}
									</div>
								{/each}
								{#if activeReview.status === 'complete'}
									<button
										class="btn"
										disabled={busy || !hasAnyAnswer}
										onclick={() => sendAnswers(activeReview)}
									>
										Send answers to coach
									</button>
								{/if}
							</section>
						{/if}
						{#if activeReview.status === 'complete'}
							<section class="review-conversation" aria-labelledby="review-conversation-heading">
								<div class="review-conversation-head">
									<div>
										<h3 id="review-conversation-heading">Discuss this review</h3>
										<p>Ask what the evidence means. To correct it, start your message with “Update the review:”.</p>
									</div>
									{#if reviewRevisions.length > 1}
										<details class="revision-history">
											<summary>{reviewRevisions.length} versions</summary>
											<ol>
												{#each reviewRevisions as revision (revision.id)}
													<li>
														<div class="revision-meta">
															<span>Version {revision.version}</span>
															<span>{revision.outcome.replaceAll('_', ' ')} · {revision.confidence}</span>
														</div>
														<time>{revision.created_at}</time>
														<div class="markdown-body revision-content">{@html renderMarkdown(revision.content_md)}</div>
														{#if !revision.snapshot_complete}
															<p class="revision-legacy-note">Legacy partial snapshot — fields not recorded at the time are shown as unavailable.</p>
														{/if}
														<details class="revision-evidence">
															<summary>Audit details</summary>
															<dl>
																<div>
																	<dt>References</dt>
																	<dd>
																		{#each revision.refs as ref, index (index)}
																			<code>{ref.kind}:{ref.value}</code>
																		{:else}None{/each}
																	</dd>
																</div>
																<div>
																	<dt>Follow-up questions</dt>
																	<dd>
																		{#each revision.follow_up_questions as question, index (index)}
																			<span>{question}</span>
																		{:else}{revision.snapshot_complete ? 'None' : 'Unavailable'}{/each}
																	</dd>
																</div>
																<div>
																	<dt>Plot observations</dt>
																	<dd>
																		{#each revision.plot_observations as observation, index (index)}
																			<span><code>{observation.plot}</code> — {observation.observation}</span>
																		{:else}{revision.snapshot_complete ? 'None' : 'Unavailable'}{/each}
																	</dd>
																</div>
																<div>
																	<dt>Historical evidence</dt>
																	<dd>
																		{#each revision.history_used as evidence, index (index)}
																			<span>
																				<code>{evidence.run_id}</code> · {evidence.role.replaceAll('_', ' ')} — {evidence.reason}
																				({evidence.refs.map((ref) => `${ref.kind}:${ref.value}`).join(', ')})
																			</span>
																		{:else}{revision.snapshot_complete ? 'None' : 'Unavailable'}{/each}
																	</dd>
																</div>
																<div>
																	<dt>Measurement assessment</dt>
																	<dd>
																		{#if revision.measurement_assessment}
																			<span>{revision.measurement_assessment.status} · <code>{revision.measurement_assessment.run_id}</code> / <code>{revision.measurement_assessment.occurrence_key}</code></span>
																			<span>{revision.measurement_assessment.rationale}</span>
																		{:else}{revision.snapshot_complete ? 'None' : 'Unavailable'}{/if}
																	</dd>
																</div>
															</dl>
														</details>
													</li>
												{/each}
											</ol>
										</details>
									{/if}
								</div>
								<div class="review-message-list" bind:this={reviewMessagePane}>
									{#each reviewMessages as message (message.id)}
										<article class="message" class:coach={message.role === 'coach'} class:system={message.role === 'system'}>
											<header>{message.role}</header>
											<div class="markdown-body">{@html renderMarkdown(message.content_md)}</div>
										</article>
									{:else}
										<p class="empty-line">No discussion yet.</p>
									{/each}
									{#if awaitingReviewCoach}
										<p class="thinking">
											{#if !status?.worker_enabled}Coach worker is paused{:else}Coach is thinking…{/if}
										</p>
									{/if}
								</div>
								<div class="review-composer">
									<textarea
										bind:value={reviewDraft}
										rows="3"
										placeholder="Discuss it, or start with “Update the review:”"
										aria-label="Message about this review"
									></textarea>
									<button class="btn primary" onclick={sendReviewMessage} disabled={busy || !reviewDraft.trim()}>Send</button>
								</div>
							</section>
						{/if}
					</div>
				{:else}
					<p class="empty-line pane-empty">No reviews yet. Request a coach debrief from the Today board.</p>
				{/if}
			</section>
		</div>
	{:else}
		<div class="workspace">
			<aside class="rail" aria-label="Coach threads">
				<h2>Threads</h2>
				<div class="new-thread-row">
					<input bind:value={newThreadTitle} placeholder="New thread title" aria-label="New thread title" />
					<button class="btn primary" onclick={createThread} disabled={busy || !newThreadTitle.trim()}>Add</button>
				</div>
				<div class="rail-scroll">
					{#each threads as thread (thread.id)}
						<button
							class="rail-row"
							class:active={thread.id === activeThreadId}
							onclick={() => chooseThread(thread.id)}
						>
							<span class="row-top">
								<span class="thread-title">{thread.title}</span>
								<span class="row-status">{thread.status.replaceAll('_', ' ')}</span>
							</span>
						</button>
					{:else}
						<p class="empty-line">No conversations.</p>
					{/each}
				</div>
			</aside>

			<section class="pane" aria-labelledby="transcript-heading">
				<div class="pane-head">
					<h2 id="transcript-heading" class="pane-title">{activeThread?.title ?? 'Conversation'}</h2>
					{#if activeThread?.status === 'open'}
						<button class="btn" onclick={closeThread} disabled={busy}>Close & remember</button>
					{:else if activeThread?.status === 'close_failed'}
						<button class="btn danger" onclick={retryClose} disabled={busy}>Retry close</button>
					{/if}
				</div>
				<div class="pane-scroll message-scroll" bind:this={messagePane}>
					{#each messages as message (message.id)}
						<article class="message" class:coach={message.role === 'coach'} class:system={message.role === 'system'}>
							<header>{message.role}</header>
							<div class="markdown-body">{@html renderMarkdown(message.content_md)}</div>
						</article>
					{:else}
						<p class="empty-line">Select or create a thread to ask a question.</p>
					{/each}
					{#if awaitingCoach}
						<p class="thinking">
							{#if !status?.worker_enabled}Coach worker is paused{:else if status.running_job && status.running_job.kind.startsWith('review')}Queued behind the current review{:else}Coach is thinking…{/if}
						</p>
					{/if}
				</div>
				{#if activeThread?.status === 'open'}
					<div class="composer">
						<textarea bind:value={draft} rows="3" placeholder="Ask about training evidence…" aria-label="Message to coach"></textarea>
						<button class="btn primary" onclick={sendMessage} disabled={busy || !draft.trim()}>Send</button>
					</div>
				{:else if activeThread}
					<p class="thread-state">Thread is {activeThread.status.replaceAll('_', ' ')}.</p>
				{/if}
			</section>
		</div>
	{/if}
</div>

<style>
	.coach-page {
		max-width: 1240px;
		margin: 0 auto;
		color: #c8d6e0;
	}
	.page-heading {
		display: flex;
		justify-content: space-between;
		align-items: center;
		padding: 2px 0 16px;
	}
	.heading-left {
		display: flex;
		align-items: center;
		gap: 20px;
	}
	h1 {
		margin: 0;
		font-size: 24px;
		font-weight: 600;
		color: #eef4f7;
	}
	.tab-switch {
		display: flex;
		gap: 2px;
		padding: 3px;
		background: #101a26;
		border: 1px solid rgba(255, 255, 255, 0.08);
		border-radius: 8px;
	}
	.tab-switch button {
		border: 0;
		background: transparent;
		color: #8194a2;
		font: 500 13px 'Instrument Sans', sans-serif;
		padding: 6px 16px;
		border-radius: 6px;
		cursor: pointer;
	}
	.tab-switch button:hover {
		color: #c8d6e0;
	}
	.tab-switch button.active {
		background: rgba(91, 181, 166, 0.14);
		color: #7fd0c2;
	}
	.worker-line {
		color: #708392;
		font-size: 13px;
	}

	.watch-strip {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 8px;
		margin: 0 0 14px;
		padding: 10px 14px;
		background: #101a26;
		border: 1px solid rgba(255, 255, 255, 0.08);
		border-radius: 10px;
	}
	.watch-label {
		flex-shrink: 0;
		color: #7a8ea0;
		font-family: 'DM Mono', monospace;
		font-size: 11px;
		font-weight: 600;
		text-transform: uppercase;
		letter-spacing: 0.07em;
	}
	.watch-item {
		padding: 4px 10px;
		background: rgba(210, 161, 95, 0.12);
		border: 1px solid rgba(210, 161, 95, 0.3);
		border-radius: 20px;
		color: #e0b986;
		font-size: 12px;
	}

	.workspace {
		display: grid;
		grid-template-columns: 280px minmax(0, 1fr);
		gap: 16px;
		height: calc(100vh - 190px);
		min-height: 520px;
	}
	.rail,
	.pane {
		background: #101a26;
		border: 1px solid rgba(255, 255, 255, 0.08);
		border-radius: 10px;
		min-height: 0;
		display: flex;
		flex-direction: column;
	}
	.rail {
		padding: 16px 12px;
	}
	.rail h2 {
		margin: 0 8px 10px;
		font-size: 11px;
		font-weight: 600;
		text-transform: uppercase;
		letter-spacing: 0.07em;
		color: #7a8ea0;
	}
	.rail-scroll {
		overflow-y: auto;
		min-height: 0;
		flex: 1;
	}
	.rail-row {
		width: 100%;
		display: grid;
		gap: 3px;
		text-align: left;
		border: 0;
		background: transparent;
		border-radius: 7px;
		padding: 9px 10px;
		color: #aabac4;
		cursor: pointer;
		font: 13px 'Instrument Sans', sans-serif;
	}
	.rail-row:hover {
		background: rgba(255, 255, 255, 0.04);
		color: #dbe6ec;
	}
	.rail-row.active {
		background: rgba(91, 181, 166, 0.11);
		color: #e6efF2;
	}
	.row-top {
		display: flex;
		justify-content: space-between;
		align-items: baseline;
		gap: 10px;
		min-width: 0;
	}
	.thread-title {
		flex: 1;
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		font-weight: 500;
	}
	.row-status {
		flex-shrink: 0;
		color: #64798a;
		font-size: 11px;
		text-transform: capitalize;
	}
	.rail-row.active .row-status {
		color: #79b8ab;
	}
	.row-sub {
		color: #64798a;
		font-size: 11.5px;
	}
	.rail-row.active .row-sub {
		color: #93a8b5;
	}
	.tabular {
		font-family: 'DM Mono', monospace;
		font-variant-numeric: tabular-nums;
		font-size: 12px;
	}

	.brief {
		margin: 10px 8px 0;
		padding-top: 12px;
		border-top: 1px solid rgba(255, 255, 255, 0.07);
	}
	.brief summary {
		cursor: pointer;
		color: #7a8ea0;
		font-size: 11px;
		font-weight: 600;
		text-transform: uppercase;
		letter-spacing: 0.07em;
	}
	.brief summary:hover {
		color: #a9bcc8;
	}
	.brief-body {
		margin-top: 10px;
		font-size: 12.5px;
		max-height: 300px;
		overflow-y: auto;
	}
	.journal {
		margin-top: 12px;
	}
	.journal-list {
		list-style: none;
		margin: 10px 0 0;
		padding: 0;
		display: flex;
		flex-direction: column;
		gap: 6px;
		max-height: 300px;
		overflow-y: auto;
	}
	.journal-entry summary {
		display: flex;
		align-items: baseline;
		gap: 8px;
		cursor: pointer;
		text-transform: none;
		letter-spacing: normal;
		font-weight: 400;
		color: #aebec8;
	}
	.journal-entry summary:hover {
		color: #dbe7ed;
	}
	.journal-entry .tabular {
		flex-shrink: 0;
		color: #7a8ea0;
	}
	.journal-takeaway {
		font-size: 12px;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.journal-body {
		margin: 8px 0 4px;
		font-size: 12px;
	}

	.pane {
		padding: 0;
	}
	.pane-head {
		display: flex;
		justify-content: space-between;
		align-items: center;
		gap: 16px;
		padding: 14px 20px;
		border-bottom: 1px solid rgba(255, 255, 255, 0.07);
	}
	.pane-title {
		margin: 0;
		font-size: 15px;
		font-weight: 600;
		color: #e6eef2;
		display: flex;
		align-items: baseline;
		gap: 10px;
	}
	.pane-date {
		color: #7a8ea0;
		font-weight: 400;
	}
	.pane-headline {
		margin: 3px 0 0;
		font-size: 15px;
		font-weight: 600;
		color: #eef5f8;
	}
	.pane-meta {
		margin: 3px 0 0;
		color: #708392;
		font-size: 12.5px;
		text-transform: capitalize;
	}
	.pane-scroll {
		overflow-y: auto;
		min-height: 0;
		flex: 1;
		padding: 18px 20px;
	}
	.pane-empty {
		padding: 18px 20px;
	}

	input,
	textarea {
		width: 100%;
		box-sizing: border-box;
		border: 1px solid rgba(255, 255, 255, 0.11);
		background: #0c151f;
		color: #dbe7ed;
		border-radius: 7px;
		padding: 9px 11px;
		font: 13px 'Instrument Sans', sans-serif;
	}
	input:focus,
	textarea:focus {
		outline: 2px solid rgba(91, 181, 166, 0.35);
		border-color: #5bb5a6;
	}
	.btn {
		border: 1px solid rgba(255, 255, 255, 0.14);
		background: rgba(255, 255, 255, 0.04);
		color: #c4d2db;
		border-radius: 7px;
		padding: 7px 14px;
		cursor: pointer;
		font: 500 12.5px 'Instrument Sans', sans-serif;
		white-space: nowrap;
	}
	.btn:hover:not(:disabled) {
		background: rgba(255, 255, 255, 0.08);
		color: #e8f0f5;
	}
	.btn.primary {
		border-color: rgba(91, 181, 166, 0.45);
		background: rgba(91, 181, 166, 0.16);
		color: #8fd6c9;
	}
	.btn.primary:hover:not(:disabled) {
		background: rgba(91, 181, 166, 0.26);
		color: #b1e6dc;
	}
	.btn.danger {
		border-color: rgba(232, 93, 74, 0.45);
		background: rgba(232, 93, 74, 0.12);
		color: #f0a08f;
	}
	.btn.danger:hover:not(:disabled) {
		background: rgba(232, 93, 74, 0.2);
	}
	.btn:disabled {
		opacity: 0.45;
		cursor: default;
	}

	.new-thread-row {
		display: grid;
		grid-template-columns: 1fr auto;
		gap: 6px;
		margin: 0 8px 12px;
	}

	.message-scroll {
		display: flex;
		flex-direction: column;
		gap: 12px;
	}
	.message {
		max-width: 78%;
		align-self: flex-end;
		padding: 11px 14px;
		background: #16283a;
		border-left: 3px solid #6389a8;
		border-radius: 8px;
	}
	.message.coach {
		align-self: flex-start;
		background: #12242b;
		border-left-color: #5bb5a6;
	}
	.message.system {
		max-width: 100%;
		align-self: stretch;
		background: rgba(210, 147, 62, 0.09);
		border-left-color: #d2933e;
	}
	.message header {
		color: #7a8ea0;
		font-size: 10.5px;
		font-weight: 600;
		text-transform: uppercase;
		letter-spacing: 0.07em;
		margin-bottom: 5px;
	}
	.composer {
		display: grid;
		grid-template-columns: 1fr auto;
		gap: 10px;
		align-items: end;
		padding: 14px 20px;
		border-top: 1px solid rgba(255, 255, 255, 0.07);
	}
	.composer .btn {
		min-width: 76px;
		height: 40px;
	}
	.thread-state {
		margin: 0;
		padding: 14px 20px;
		border-top: 1px solid rgba(255, 255, 255, 0.07);
		color: #708392;
		font-size: 12.5px;
	}
	.thinking {
		color: #6e8391;
		font-size: 12.5px;
		font-style: italic;
	}

	.markdown-body {
		color: #c8d6e0;
		font-size: 13.5px;
		line-height: 1.6;
		overflow-wrap: anywhere;
	}
	.markdown-body :global(p:first-child) {
		margin-top: 0;
	}
	.markdown-body :global(p:last-child) {
		margin-bottom: 0;
	}
	.markdown-body :global(a) {
		color: #75b5e5;
	}
	.refs {
		margin: 14px 0 0;
		color: #6e8391;
		font-size: 11.5px;
	}
	.plot-evidence {
		margin-top: 18px;
	}
	.plot-evidence h3,
	.coach-questions h3 {
		margin: 0 0 8px;
		color: #7a8ea0;
		font-size: 11px;
		font-weight: 600;
		text-transform: uppercase;
		letter-spacing: 0.07em;
	}
	.plot-list {
		display: grid;
		gap: 16px;
	}
	.plot-evidence figure {
		margin: 0;
		padding-top: 12px;
		border-top: 1px solid rgba(255, 255, 255, 0.06);
	}
	.plot-evidence img {
		display: block;
		width: 100%;
		height: auto;
		background: #0c151d;
		border: 1px solid rgba(255, 255, 255, 0.08);
		border-radius: 6px;
	}
	.plot-evidence figcaption {
		display: grid;
		grid-template-columns: minmax(0, 1fr) minmax(160px, 260px);
		gap: 18px;
		padding-top: 8px;
		color: #aebec8;
		font-size: 12.5px;
		line-height: 1.5;
	}
	.plot-evidence code {
		color: #75b5e5;
		font: 10px 'DM Mono', monospace;
		overflow-wrap: anywhere;
		text-align: right;
	}
	.plot-unavailable {
		padding: 18px;
		border: 1px dashed rgba(255, 255, 255, 0.12);
		border-radius: 6px;
		color: #708392;
		font-size: 12.5px;
	}
	.coach-questions {
		margin-top: 18px;
	}
	.question-row {
		padding: 10px 0;
		border-top: 1px solid rgba(255, 255, 255, 0.06);
	}
	.question-text {
		margin: 0 0 8px;
		color: #b6c5cf;
		font-size: 13px;
		line-height: 1.5;
	}
	.question-answer {
		display: block;
	}
	.coach-questions > .btn {
		margin-top: 12px;
	}
	.review-conversation {
		margin-top: 24px;
		padding-top: 18px;
		border-top: 1px solid rgba(255, 255, 255, 0.09);
	}
	.review-conversation-head {
		display: grid;
		gap: 20px;
	}
	.review-conversation h3 {
		margin: 0;
		color: #dce7ec;
		font-size: 14px;
		font-weight: 600;
	}
	.review-conversation-head p {
		max-width: 660px;
		margin: 4px 0 0;
		color: #708392;
		font-size: 12.5px;
		line-height: 1.5;
	}
	.revision-history {
		width: 100%;
		color: #7a8ea0;
		font-size: 11.5px;
	}
	.revision-history summary {
		cursor: pointer;
		color: #79b8ab;
	}
	.revision-history ol {
		margin: 8px 0 0;
		padding: 0;
		list-style: none;
	}
	.revision-history li {
		padding: 10px 0;
		border-top: 1px solid rgba(255, 255, 255, 0.07);
	}
	.revision-meta {
		display: flex;
		justify-content: space-between;
		gap: 16px;
		color: #94a7b3;
		text-transform: capitalize;
	}
	.revision-history time {
		display: block;
		color: #607483;
		font: 10px 'DM Mono', monospace;
	}
	.revision-content {
		margin-top: 8px;
		color: #aebec8;
		font-size: 12px;
	}
	.revision-legacy-note {
		margin: 8px 0 0;
		color: #d2a15f;
	}
	.revision-evidence {
		margin-top: 8px;
	}
	.revision-evidence summary {
		color: #708fa3;
	}
	.revision-evidence dl {
		margin: 8px 0 0;
	}
	.revision-evidence dl > div {
		display: grid;
		grid-template-columns: 140px minmax(0, 1fr);
		gap: 14px;
		padding: 6px 0;
		border-top: 1px solid rgba(255, 255, 255, 0.05);
	}
	.revision-evidence dt {
		color: #718593;
	}
	.revision-evidence dd {
		display: grid;
		gap: 4px;
		margin: 0;
		color: #a6b7c2;
		line-height: 1.45;
	}
	.revision-evidence code {
		color: #75b5e5;
		font: 10.5px 'DM Mono', monospace;
	}
	.review-message-list {
		display: flex;
		flex-direction: column;
		gap: 10px;
		max-height: 360px;
		margin-top: 14px;
		padding: 2px 4px 2px 0;
		overflow-y: auto;
	}
	.review-composer {
		display: grid;
		grid-template-columns: minmax(0, 1fr) auto;
		align-items: end;
		gap: 10px;
		margin-top: 12px;
	}
	.review-composer .btn {
		min-width: 76px;
		height: 40px;
	}
	.empty-line,
	.loading-line {
		color: #617481;
		font-size: 13px;
		margin: 4px 8px;
	}
	.error-line {
		color: #f08a78;
		border-left: 3px solid #e85d4a;
		padding: 8px 12px;
		margin: 0 0 12px;
	}

	.failure-reason {
		white-space: pre-wrap;
		overflow-wrap: anywhere;
	}
</style>
