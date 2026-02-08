<script lang="ts">
	import '../app.css';
	import favicon from '$lib/assets/favicon.svg';
	import { page } from '$app/state';

	let { children } = $props();

	const tabs = [
		{ href: '/', label: 'Dashboard' },
		{ href: '/heart-rate', label: 'Heart Rate' },
		{ href: '/hrv', label: 'HRV' },
		{ href: '/respiration', label: 'Respiration' },
		{ href: '/skin-temp', label: 'Skin Temp' },
		{ href: '/pulse-ox', label: 'Pulse Ox' }
	];
</script>

<svelte:head>
	<link rel="icon" href={favicon} />
	<title>Garmin Stats</title>
</svelte:head>

<div class="min-h-screen bg-gray-50">
	<header class="bg-white shadow-sm border-b border-gray-200">
		<div class="max-w-7xl mx-auto px-4 py-4">
			<h1 class="text-2xl font-bold text-gray-900">Garmin Stats</h1>
			<p class="text-sm text-gray-500">Epix Gen 2 Health Data Analysis</p>
		</div>
		<nav class="max-w-7xl mx-auto px-4 overflow-x-auto">
			<div class="flex gap-1 -mb-px">
				{#each tabs as tab}
					<a
						href={tab.href}
						class="px-4 py-2 text-sm font-medium whitespace-nowrap border-b-2 transition-colors {page
							.url.pathname === tab.href
							? 'border-blue-600 text-blue-600'
							: 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'}"
					>
						{tab.label}
					</a>
				{/each}
			</div>
		</nav>
	</header>

	<main class="max-w-7xl mx-auto px-4 py-6">
		{@render children()}
	</main>
</div>
