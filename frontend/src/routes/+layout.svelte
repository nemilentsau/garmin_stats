<script lang="ts">
	import '../app.css';
	import favicon from '$lib/assets/favicon.svg';

	let { children } = $props();
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
	</header>

	<main class="max-w-7xl mx-auto px-4 py-6">
		{@render children()}
	</main>
</div>
