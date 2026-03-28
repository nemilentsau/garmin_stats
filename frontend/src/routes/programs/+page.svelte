<svelte:head>
	<title>Programs - Garmin Stats</title>
</svelte:head>

<section class="placeholder-shell">
	<div class="placeholder-card">
		<p class="eyebrow">Unplugged Surface</p>
		<h1>Programs are intentionally offline.</h1>
		<p>
			The old program import flow is parked while routines move to the assistant artifact pipeline. New
			plans should enter through structured drafts on <a href="/routines">Routines</a>, then compile into
			live cards and schedules after review.
		</p>
		<div class="link-row">
			<a href="/routines">Open routine studio</a>
			<a href="/assistant">Open assistant</a>
		</div>
	</div>
</section>

<style>
	.placeholder-shell {
		display: grid;
		place-items: center;
		min-height: 58vh;
	}

	.placeholder-card {
		max-width: 720px;
		padding: 28px;
		border-radius: 28px;
		border: 1px solid rgba(255, 255, 255, 0.08);
		background:
			radial-gradient(circle at top left, rgba(91, 181, 166, 0.16), transparent 35%),
			rgba(255, 255, 255, 0.03);
	}

	.eyebrow {
		margin: 0;
		font-family: 'DM Mono', monospace;
		font-size: 11px;
		letter-spacing: 0.16em;
		text-transform: uppercase;
		color: #8fa3b0;
	}

	h1 {
		margin: 12px 0;
		font-size: clamp(30px, 5vw, 46px);
		line-height: 1.02;
	}

	p {
		color: #a8bac6;
		line-height: 1.6;
	}

	.link-row {
		display: flex;
		flex-wrap: wrap;
		gap: 10px;
		margin-top: 18px;
	}

	a {
		padding: 12px 14px;
		border-radius: 999px;
		background: rgba(255, 255, 255, 0.06);
		color: #eef5f8;
		text-decoration: none;
	}
</style>
