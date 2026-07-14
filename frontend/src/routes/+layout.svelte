<script lang="ts">
	import '../app.css';
	import favicon from '$lib/assets/favicon.svg';
	import { page } from '$app/state';

	let { children } = $props();

	function pathMatches(pathname: string, href: string): boolean {
		if (href === '/') return pathname === '/';
		return pathname === href || pathname.startsWith(`${href}/`);
	}

	const sections = [
		{
			label: 'Dashboard',
			href: '/',
			subtabs: [
				{ href: '/', label: 'Overview' },
				{ href: '/heart-rate', label: 'Heart Rate' },
				{ href: '/hrv', label: 'HRV' },
				{ href: '/sleep', label: 'Sleep' },
				{ href: '/stress', label: 'Stress' },
				{ href: '/body-battery', label: 'Body Battery' },
				{ href: '/respiration', label: 'Respiration' },
				{ href: '/skin-temp', label: 'Skin Temp' },
				{ href: '/pulse-ox', label: 'Pulse Ox' }
			]
		},
		{
			label: 'Training',
			href: '/today',
			subtabs: [
				{ href: '/today', label: 'Today' },
				{ href: '/training/schedule', label: 'Schedule' },
				{ href: '/runs', label: 'Runs' },
				{ href: '/experiments', label: 'Experiments' },
				{ href: '/training/import', label: 'Import' }
			]
		},
		{
			label: 'Coach',
			href: '/coach',
			subtabs: []
		}
	];

	const activeSection = $derived.by(
		() =>
			sections.find((section) => section.subtabs.some((tab) => pathMatches(page.url.pathname, tab.href))) ??
			sections.find((section) => pathMatches(page.url.pathname, section.href)) ??
			sections[0]
	);
</script>

<svelte:head>
	<link rel="icon" href={favicon} />
	<link rel="preconnect" href="https://fonts.googleapis.com" />
	<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin="anonymous" />
	<link href="https://fonts.googleapis.com/css2?family=DM+Mono:wght@300;400;500&family=Instrument+Sans:wght@400;500;600;700&display=swap" rel="stylesheet" />
	<title>Garmin Stats</title>
</svelte:head>

<div class="topo-page">
	<!-- Header -->
	<header class="topo-header">
		<div class="header-left">
			<div class="header-icon">
				<svg width="28" height="28" viewBox="0 0 28 28" fill="none">
					<path d="M4 20 L8 12 L12 16 L18 6 L24 14" stroke="#5BB5A6" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
					<path d="M4 22 L10 17 L15 20 L20 10 L24 16" stroke="#4A90D9" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" fill="none" opacity="0.5"/>
				</svg>
			</div>
			<div>
				<h1 class="header-title">GARMIN HEALTH</h1>
				<p class="header-sub">Epix Gen 2</p>
			</div>
		</div>
		<nav class="header-nav">
			{#each sections as section}
				<a
					href={section.href}
					class={activeSection === section ? 'active' : ''}
				>{section.label}</a>
			{/each}
		</nav>
	</header>

	{#if activeSection.subtabs.length > 0}
		<nav class="subtab-bar">
			{#each activeSection.subtabs as tab}
				<a href={tab.href} class={pathMatches(page.url.pathname, tab.href) ? 'active' : ''}>{tab.label}</a>
			{/each}
		</nav>
	{/if}

	<main class="topo-content">
		{@render children()}
	</main>
</div>

<style>
	.topo-page {
		min-height: 100vh;
		background: #0d1520;
		color: #c8d6e0;
		font-family: 'Instrument Sans', sans-serif;
		position: relative;
		overflow-x: hidden;
	}

	.topo-header {
		position: relative;
		z-index: 1;
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 16px 28px;
		border-bottom: 1px solid rgba(255,255,255,0.06);
		backdrop-filter: blur(12px);
		background: rgba(13,21,32,0.8);
	}

	.header-left {
		display: flex;
		align-items: center;
		gap: 12px;
	}

	.header-icon {
		width: 40px;
		height: 40px;
		border-radius: 10px;
		background: rgba(91,181,166,0.1);
		border: 1px solid rgba(91,181,166,0.2);
		display: flex;
		align-items: center;
		justify-content: center;
	}

	.header-title {
		font-family: 'Instrument Sans', sans-serif;
		font-size: 15px;
		font-weight: 700;
		letter-spacing: 3px;
		color: #e8f0f5;
		margin: 0;
	}

	.header-sub {
		font-family: 'DM Mono', monospace;
		font-size: 11px;
		color: #5e7282;
		letter-spacing: 1px;
		margin: 0;
	}

	.header-nav {
		display: flex;
		gap: 4px;
	}

	.header-nav a {
		font-family: 'DM Mono', monospace;
		font-size: 11px;
		padding: 6px 12px;
		border-radius: 6px;
		color: #5e7282;
		text-decoration: none;
		transition: all 0.2s;
	}

	.header-nav a:hover { color: #c8d6e0; background: rgba(255,255,255,0.05); }
	.header-nav a.active { color: #5BB5A6; background: rgba(91,181,166,0.1); }

	.subtab-bar {
		position: relative;
		z-index: 1;
		display: flex;
		gap: 2px;
		padding: 8px 28px;
		border-bottom: 1px solid rgba(255,255,255,0.04);
		background: rgba(13,21,32,0.6);
		backdrop-filter: blur(8px);
	}

	.subtab-bar a {
		font-family: 'DM Mono', monospace;
		font-size: 11px;
		padding: 4px 10px;
		border-radius: 4px;
		color: #4a5e6d;
		text-decoration: none;
		transition: all 0.2s;
	}

	.subtab-bar a:hover { color: #8fa3b0; }
	.subtab-bar a.active { color: #5BB5A6; background: rgba(91,181,166,0.08); }

	.topo-content {
		position: relative;
		z-index: 1;
		max-width: 1400px;
		margin: 0 auto;
		padding: 24px 28px;
	}

	@media (max-width: 720px) {
		.topo-header {
			flex-direction: column;
			align-items: flex-start;
			gap: 14px;
		}

		.header-nav,
		.subtab-bar {
			flex-wrap: wrap;
		}
	}
</style>
