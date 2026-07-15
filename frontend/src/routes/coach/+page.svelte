<script lang="ts">
	import { onDestroy, onMount } from 'svelte';
	import { page } from '$app/state';
	import {
		api,
		type CoachBriefResponse,
		type CoachMessage,
		type CoachReview,
		type CoachStatus,
		type CoachThread
	} from '$lib/api';
	import { renderMarkdown } from '$lib/markdown';
	import { startRealtimePage } from '$lib/realtime-page';
	import { createCoachUpdateListener } from '$lib/sse';
	import { errorMessage } from '$lib/utils';

	let status: CoachStatus | null = $state(null);
	let reviews: CoachReview[] = $state([]);
	let threads: CoachThread[] = $state([]);
	let messages: CoachMessage[] = $state([]);
	let brief: CoachBriefResponse | null = $state(null);
	let activeThreadId: string | null = $state(null);
	let activeReviewId: string | null = $state(null);
	let loading = $state(true);
	let error: string | null = $state(null);
	let draft = $state('');
	let newThreadTitle = $state('');
	let busy = $state(false);

	let activeThread = $derived(threads.find((thread) => thread.id === activeThreadId) ?? null);
	let activeReview = $derived(
		reviews.find((review) => review.id === activeReviewId) ?? reviews[0] ?? null
	);
	let awaitingCoach = $derived(messages.length > 0 && messages[messages.length - 1]?.role === 'user');

	function reviewOutcome(review: CoachReview): string {
		const outcome = (review.outcome ?? review.verdict ?? 'not assessed').replaceAll('_', ' ');
		return review.outcome && (review.status === 'queued' || review.status === 'generating')
			? `previous: ${outcome}`
			: outcome;
	}

	async function refreshMessages(threadId: string | null): Promise<void> {
		messages = threadId ? (await api.getCoachMessages(threadId)).messages : [];
	}

	async function refreshAll(): Promise<void> {
		const [nextStatus, nextReviews, nextThreads, nextBrief] = await Promise.all([
			api.getCoachStatus(),
			api.getCoachReviews({ limit: 100 }),
			api.getCoachThreads(),
			api.getCoachBrief()
		]);
		status = nextStatus;
		reviews = nextReviews.reviews;
		threads = nextThreads.threads;
		brief = nextBrief;
		const requestedReview = page.url.searchParams.get('review');
		if (requestedReview && reviews.some((review) => review.id === requestedReview)) {
			activeReviewId = requestedReview;
		} else if (!activeReviewId && reviews[0]) {
			activeReviewId = reviews[0].id;
		}
		if (!activeThreadId || !threads.some((thread) => thread.id === activeThreadId)) {
			activeThreadId = threads[0]?.id ?? null;
		}
		await refreshMessages(activeThreadId);
		error = null;
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

	async function regenerateReview(reviewId: string): Promise<void> {
		if (busy) return;
		busy = true;
		try {
			await api.regenerateCoachReview(reviewId);
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
		<div>
			<p class="eyebrow">TRAINING REVIEW & MEMORY</p>
			<h1>Coach</h1>
		</div>
		<div class="worker-state">
			<strong>{status?.worker_enabled ? 'Worker active' : 'Coach worker is paused'}</strong>
			<span>
				{#if status?.running_job}Running {status.running_job.kind.replaceAll('_', ' ')}{:else}{status?.queued_count ?? 0} queued{/if}
			</span>
		</div>
	</header>

	{#if error}<p class="error-line" role="alert">{error}</p>{/if}
	{#if loading}
		<p class="loading-line">Loading coach workspace…</p>
	{:else}
		<section class="latest-review" aria-labelledby="latest-review-heading">
			<div class="section-heading-row">
				<h2 id="latest-review-heading">Latest review</h2>
				{#if activeReview}<span class="status-label">{activeReview.status.replaceAll('_', ' ')}</span>{/if}
			</div>
			{#if activeReview}
				<div class="review-meta">
					<span class="tabular">{activeReview.date}</span>
					<span>{activeReview.kind === 'run' ? 'Run review' : 'Missed-run review'}</span>
					<span>{reviewOutcome(activeReview)}</span>
					{#if activeReview.confidence}<span>{activeReview.confidence} confidence</span>{/if}
				</div>
				{#if activeReview.content_md}
					{#if activeReview.status === 'queued' || activeReview.status === 'generating'}
						<p class="muted">Previous completed review shown while regeneration is {activeReview.status}.</p>
					{/if}
					<div class="markdown-body">{@html renderMarkdown(activeReview.content_md)}</div>
			{:else}
					<p class="muted">This review is {activeReview.status.replaceAll('_', ' ')}. Its evidence-backed response will appear here.</p>
				{/if}
				{#if activeReview.refs.length > 0}
					<p class="refs">Evidence: {activeReview.refs.map((ref) => `${ref.kind}:${ref.value}`).join(' · ')}</p>
				{/if}
				{#if activeReview.plot_observations.length > 0}
					<section class="plot-evidence" aria-labelledby="plot-evidence-heading">
						<h3 id="plot-evidence-heading">Plot evidence used</h3>
						<ul>
							{#each activeReview.plot_observations as observation (`${observation.plot}:${observation.observation}`)}
								<li>
									<span class="plot-name">{observation.plot}</span>
									<span>{observation.observation}</span>
								</li>
							{/each}
						</ul>
					</section>
				{/if}
				{#if activeReview.follow_up_questions.length > 0}
					<section class="coach-questions" aria-labelledby="coach-questions-heading">
						<h3 id="coach-questions-heading">Coach questions</h3>
						<ul>
							{#each activeReview.follow_up_questions as question (question)}
								<li>{question}</li>
							{/each}
						</ul>
					</section>
				{/if}
				{#if activeReview.status === 'failed'}
					<button class="text-action" onclick={() => retryReview(activeReview.id)} disabled={busy}>Retry review</button>
				{:else if activeReview.status === 'complete'}
					<button class="text-action" onclick={() => regenerateReview(activeReview.id)} disabled={busy}>Regenerate review</button>
				{/if}
			{:else}
				<p class="empty-line">No reviews yet. Open a run and choose “Review with coach.”</p>
			{/if}
		</section>

		<div class="conversation-layout">
			<aside class="thread-rail" aria-label="Coach threads">
				<div class="section-heading-row"><h2>Threads</h2></div>
				<div class="new-thread-row">
					<input bind:value={newThreadTitle} placeholder="New thread title" aria-label="New thread title" />
					<button onclick={createThread} disabled={busy || !newThreadTitle.trim()}>Add</button>
				</div>
				{#each threads as thread (thread.id)}
					<button class:active={thread.id === activeThreadId} class="thread-row" onclick={() => chooseThread(thread.id)}>
						<span>{thread.title}</span><small>{thread.status.replaceAll('_', ' ')}</small>
					</button>
				{:else}
					<p class="empty-line">No conversations.</p>
				{/each}
			</aside>

			<section class="transcript" aria-labelledby="transcript-heading">
				<div class="section-heading-row">
					<h2 id="transcript-heading">{activeThread?.title ?? 'Conversation'}</h2>
					{#if activeThread?.status === 'open'}
						<button class="text-action" onclick={closeThread} disabled={busy}>Close & remember</button>
					{:else if activeThread?.status === 'close_failed'}
						<button class="text-action danger" onclick={retryClose} disabled={busy}>Retry close</button>
					{/if}
				</div>
				<div class="message-scroll">
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
						<button onclick={sendMessage} disabled={busy || !draft.trim()}>Send</button>
					</div>
				{:else if activeThread}
					<p class="thread-state">Thread is {activeThread.status.replaceAll('_', ' ')}.</p>
				{/if}
			</section>
		</div>

		<div class="lower-grid">
			<section>
				<h2>Review history</h2>
				{#each reviews as review (review.id)}
					<button class:active={review.id === activeReview?.id} class="review-row" onclick={() => (activeReviewId = review.id)}>
						<span class="tabular">{review.date}</span><span>{review.kind}</span><span>{review.status.replaceAll('_', ' ')}</span><span>{reviewOutcome(review)}{review.confidence ? ` · ${review.confidence} confidence` : ''}</span>
					</button>
				{:else}<p class="empty-line">No review history.</p>{/each}
			</section>
			<section>
				<details class="brief" open>
					<summary>Coach brief</summary>
					{#if brief?.brief}<div class="markdown-body">{@html renderMarkdown(brief.brief.content_md)}</div>{:else}<p class="empty-line">No durable brief yet.</p>{/if}
				</details>
			</section>
		</div>
	{/if}
</div>

<style>
	.coach-page { max-width: 1180px; margin: 0 auto; color: #c8d6e0; }
	.page-heading { display: flex; justify-content: space-between; align-items: flex-end; padding: 8px 0 20px; border-bottom: 1px solid rgba(255,255,255,.08); }
	.eyebrow, h2, .status-label, .worker-state span, .refs, .thinking, .thread-state { font-family: 'DM Mono', monospace; }
	.eyebrow { margin: 0 0 5px; color: #5bb5a6; font-size: 10px; letter-spacing: .12em; }
	h1 { margin: 0; font-size: 30px; color: #eef4f7; }
	h2 { margin: 0; font-size: 11px; text-transform: uppercase; letter-spacing: .08em; color: #8194a2; }
	.worker-state { text-align: right; display: grid; gap: 3px; }
	.worker-state strong { color: #d8e4ea; font-size: 13px; }
	.worker-state span { color: #657987; font-size: 10px; }
	.latest-review { min-height: 160px; padding: 20px 0 22px; border-bottom: 1px solid rgba(255,255,255,.08); }
	.section-heading-row { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 13px; }
	.status-label { color: #5bb5a6; font-size: 10px; text-transform: uppercase; }
	.review-meta { display: flex; gap: 16px; color: #708392; font-size: 12px; margin-bottom: 12px; text-transform: capitalize; }
	.tabular { font-family: 'DM Mono', monospace; font-variant-numeric: tabular-nums; }
	.conversation-layout { display: grid; grid-template-columns: 250px minmax(0,1fr); min-height: 480px; border-bottom: 1px solid rgba(255,255,255,.08); }
	.thread-rail { padding: 20px 18px 20px 0; border-right: 1px solid rgba(255,255,255,.08); }
	.transcript { padding: 20px 0 20px 24px; min-width: 0; display: grid; grid-template-rows: auto minmax(280px,1fr) auto; }
	.new-thread-row { display: grid; grid-template-columns: 1fr auto; gap: 6px; margin-bottom: 14px; }
	input, textarea { width: 100%; box-sizing: border-box; border: 1px solid rgba(255,255,255,.11); background: #101c28; color: #dbe7ed; border-radius: 4px; padding: 9px 10px; font: inherit; }
	input:focus, textarea:focus { outline: 2px solid rgba(91,181,166,.35); border-color: #5bb5a6; }
	button { border: 1px solid rgba(91,181,166,.3); background: rgba(91,181,166,.09); color: #8bd1c5; border-radius: 4px; padding: 7px 10px; cursor: pointer; font-family: 'DM Mono', monospace; font-size: 10px; }
	button:disabled { opacity: .45; cursor: default; }
	.thread-row, .review-row { width: 100%; border: 0; border-radius: 0; background: transparent; color: #aabac4; display: flex; justify-content: space-between; gap: 10px; text-align: left; padding: 9px 7px; border-top: 1px solid rgba(255,255,255,.05); }
	.thread-row:hover, .review-row:hover, .thread-row.active, .review-row.active { background: rgba(91,181,166,.07); color: #e2ecef; }
	.thread-row small { color: #5f7381; text-transform: capitalize; }
	.message-scroll { overflow: auto; padding-right: 8px; }
	.message { max-width: 82%; margin: 0 0 13px auto; padding: 11px 13px; background: #132230; border-left: 2px solid #58758d; border-radius: 2px; }
	.message.coach { margin-left: 0; margin-right: auto; background: #111f29; border-color: #5bb5a6; }
	.message.system { max-width: 100%; margin-left: 0; background: rgba(210,147,62,.08); border-color: #d2933e; }
	.message header { color: #657987; font: 9px 'DM Mono', monospace; text-transform: uppercase; letter-spacing: .1em; margin-bottom: 6px; }
	.composer { display: grid; grid-template-columns: 1fr auto; gap: 10px; align-items: end; padding-top: 13px; border-top: 1px solid rgba(255,255,255,.06); }
	.composer button { min-width: 74px; height: 38px; }
	.lower-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 34px; padding: 22px 0 50px; }
	.lower-grid h2 { margin-bottom: 12px; }
	.review-row { display: grid; grid-template-columns: 95px 70px 1fr 1fr; }
	.brief { border-top: 1px solid rgba(255,255,255,.07); padding-top: 10px; }
	.brief summary { cursor: pointer; color: #8194a2; font: 11px 'DM Mono', monospace; text-transform: uppercase; letter-spacing: .08em; }
	.markdown-body { color: #c8d6e0; font-size: 14px; line-height: 1.55; overflow-wrap: anywhere; }
	.markdown-body :global(p:first-child) { margin-top: 0; }
	.markdown-body :global(a) { color: #75b5e5; }
	.refs, .thinking, .thread-state { color: #6e8391; font-size: 10px; }
	.plot-evidence { margin: 16px 0 12px; }
	.plot-evidence h3 { margin: 0 0 6px; color: #8194a2; font: 10px 'DM Mono', monospace; text-transform: uppercase; letter-spacing: .08em; }
	.plot-evidence ul { list-style: none; margin: 0; padding: 0; }
	.plot-evidence li { display: grid; grid-template-columns: minmax(180px, 240px) 1fr; gap: 14px; padding: 8px 0; border-top: 1px solid rgba(255,255,255,.06); color: #aebec8; font-size: 12px; line-height: 1.45; }
	.plot-name { color: #75b5e5; font-family: 'DM Mono', monospace; font-size: 10px; overflow-wrap: anywhere; }
	.coach-questions { margin: 16px 0 12px; }
	.coach-questions h3 { margin: 0 0 6px; color: #8194a2; font: 10px 'DM Mono', monospace; text-transform: uppercase; letter-spacing: .08em; }
	.coach-questions ul { list-style: none; margin: 0; padding: 0; }
	.coach-questions li { padding: 8px 0; border-top: 1px solid rgba(255,255,255,.06); color: #aebec8; font-size: 12px; line-height: 1.45; }
	.empty-line, .loading-line { color: #617481; font-size: 13px; }
	.error-line { color: #f08a78; border-left: 2px solid #e85d4a; padding: 8px 12px; }
	.text-action { background: transparent; border: 0; padding: 2px 0; }
	.text-action.danger { color: #ef967f; }
	@media (max-width: 800px) { .conversation-layout, .lower-grid { grid-template-columns: 1fr; } .thread-rail { border-right: 0; border-bottom: 1px solid rgba(255,255,255,.08); padding-right: 0; } .transcript { padding-left: 0; } }
</style>
