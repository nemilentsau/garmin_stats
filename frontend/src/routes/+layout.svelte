<script lang="ts">
	import '../app.css';
	import favicon from '$lib/assets/favicon.svg';
	import { page } from '$app/state';

	let { children } = $props();

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
				{ href: '/routines', label: 'Routines' },
				{ href: '/experiments', label: 'Experiments' },
				{ href: '/programs', label: 'Programs' }
			]
		},
		{
			label: 'Assistant',
			href: '/assistant',
			subtabs: []
		}
	];

	const activeSection = $derived(
		sections.find((s) =>
			s.subtabs.some((t) => t.href === page.url.pathname)
		) ??
			sections.find((s) => s.href === page.url.pathname) ??
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
	<!-- SVG topo pattern background -->
	<svg class="topo-bg" xmlns="http://www.w3.org/2000/svg">
		<defs>
			<filter id="topo-noise">
				<feTurbulence type="fractalNoise" baseFrequency="0.015" numOctaves="4" seed="2" />
				<feColorMatrix type="saturate" values="0" />
				<feComponentTransfer>
					<feFuncA type="linear" slope="0.06" />
				</feComponentTransfer>
			</filter>
			<pattern id="topo-lines" x="0" y="0" width="200" height="200" patternUnits="userSpaceOnUse">
				<path d="M0,40 Q50,20 100,40 T200,40" fill="none" stroke="rgba(255,255,255,0.03)" stroke-width="1"/>
				<path d="M0,80 Q60,55 120,80 T200,80" fill="none" stroke="rgba(255,255,255,0.025)" stroke-width="1"/>
				<path d="M0,120 Q40,100 100,120 T200,120" fill="none" stroke="rgba(255,255,255,0.02)" stroke-width="1"/>
				<path d="M0,160 Q70,140 130,165 T200,160" fill="none" stroke="rgba(255,255,255,0.03)" stroke-width="1"/>
			</pattern>
		</defs>
		<rect width="100%" height="100%" filter="url(#topo-noise)" />
		<rect width="100%" height="100%" fill="url(#topo-lines)" />
	</svg>

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
				<a href={tab.href} class={page.url.pathname === tab.href ? 'active' : ''}>{tab.label}</a>
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

	.topo-bg {
		position: fixed;
		inset: 0;
		width: 100%;
		height: 100%;
		pointer-events: none;
		z-index: 0;
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
</style>
