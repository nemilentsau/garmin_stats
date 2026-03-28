<svelte:head>
	<title>Experiments - Garmin Stats</title>
</svelte:head>

<section class="placeholder-shell">
	<div class="placeholder-card">
		<p class="eyebrow">Next Layer</p>
		<h1>Experiments will return on top of the new routine runtime.</h1>
		<p>
			They are disabled for now because the old model depended on the broken routine/program structure. The
			first job is to make cards and schedules stable enough that experiments can reference them cleanly
			later.
		</p>
		<div class="link-row">
			<a href="/routines">Review draft inbox</a>
			<a href="/today">Open today board</a>
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
			radial-gradient(circle at top right, rgba(155, 107, 205, 0.18), transparent 38%),
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
