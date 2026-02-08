<script lang="ts">
	import { onMount } from "svelte";
	import { api, type OverviewStats } from "$lib/api";

	let overviewPromise: Promise<OverviewStats> = new Promise(() => {});

	onMount(() => {
		overviewPromise = api.getOverview();
	});

	function formatNumber(n: number | null): string {
		if (n === null) return "-";
		return n.toLocaleString();
	}
</script>

{#await overviewPromise}
	<div class="flex items-center justify-center h-64">
		<div class="text-gray-500">Loading data...</div>
	</div>
{:then overview}
	<!-- Overview Cards -->
	<div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
		<!-- Days Card -->
		<div class="bg-white rounded-lg shadow p-6">
			<div
				class="text-sm font-medium text-gray-500 uppercase tracking-wide"
			>
				Days of Data
			</div>
			<div class="mt-2 text-3xl font-bold text-gray-900">
				{overview.total_days}
			</div>
			<div class="mt-1 text-sm text-gray-500">
				{overview.days_available[0]} to {overview.days_available[
					overview.days_available.length - 1
				]}
			</div>
		</div>

		<!-- Heart Rate Card -->
		<div class="bg-white rounded-lg shadow p-6">
			<div
				class="text-sm font-medium text-gray-500 uppercase tracking-wide"
			>
				Heart Rate
			</div>
			<div class="mt-2 text-3xl font-bold text-red-600">
				{formatNumber(overview.heart_rate.avg)}
				<span class="text-lg font-normal">bpm</span>
			</div>
			<div class="mt-1 text-sm text-gray-500">
				{formatNumber(overview.heart_rate.min)} - {formatNumber(
					overview.heart_rate.max,
				)} bpm
			</div>
			<div class="mt-1 text-xs text-gray-400">
				{formatNumber(overview.heart_rate.total_readings)} readings
			</div>
		</div>

		<!-- Stress Card -->
		<div class="bg-white rounded-lg shadow p-6">
			<div
				class="text-sm font-medium text-gray-500 uppercase tracking-wide"
			>
				Stress Level
			</div>
			<div class="mt-2 text-3xl font-bold text-orange-600">
				{formatNumber(overview.stress.avg)}
			</div>
			<div class="mt-1 text-sm text-gray-500">
				{formatNumber(overview.stress.min)} - {formatNumber(
					overview.stress.max,
				)}
			</div>
			<div class="mt-1 text-xs text-gray-400">
				{formatNumber(overview.stress.total_readings)} readings
			</div>
		</div>

		<!-- SpO2 Card -->
		<div class="bg-white rounded-lg shadow p-6">
			<div
				class="text-sm font-medium text-gray-500 uppercase tracking-wide"
			>
				SpO2
			</div>
			<div class="mt-2 text-3xl font-bold text-blue-600">
				{formatNumber(overview.spo2.avg)}<span
					class="text-lg font-normal">%</span
				>
			</div>
			<div class="mt-1 text-sm text-gray-500">
				{formatNumber(overview.spo2.min)} - {formatNumber(
					overview.spo2.max,
				)}%
			</div>
			<div class="mt-1 text-xs text-gray-400">
				{formatNumber(overview.spo2.total_readings)} readings
			</div>
		</div>
	</div>

	<!-- Second Row -->
	<div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-8">
		<!-- Respiration Card -->
		<div class="bg-white rounded-lg shadow p-6">
			<div
				class="text-sm font-medium text-gray-500 uppercase tracking-wide"
			>
				Respiration Rate
			</div>
			<div class="mt-2 text-3xl font-bold text-teal-600">
				{formatNumber(overview.respiration.avg)}
				<span class="text-lg font-normal">br/min</span>
			</div>
			<div class="mt-1 text-sm text-gray-500">
				{formatNumber(overview.respiration.min)} - {formatNumber(
					overview.respiration.max,
				)} br/min
			</div>
			<div class="mt-1 text-xs text-gray-400">
				{formatNumber(overview.respiration.total_readings)} readings
			</div>
		</div>

		<!-- Activity Distribution -->
		<div class="bg-white rounded-lg shadow p-6">
			<div
				class="text-sm font-medium text-gray-500 uppercase tracking-wide mb-4"
			>
				Activity Distribution
			</div>
			{#each Object.entries(overview.activity_distribution).sort((a, b) => b[1] - a[1]) as [activity, count]}
				{@const total = Object.values(
					overview.activity_distribution,
				).reduce((a, b) => a + b, 0)}
				{@const pct = ((count / total) * 100).toFixed(1)}
				<div class="mb-2">
					<div class="flex justify-between text-sm mb-1">
						<span class="capitalize text-gray-700">{activity}</span>
						<span class="text-gray-500">{pct}%</span>
					</div>
					<div class="w-full bg-gray-200 rounded-full h-2">
						<div
							class="h-2 rounded-full"
							class:bg-gray-400={activity === "sedentary"}
							class:bg-green-500={activity === "walking"}
							class:bg-blue-500={activity === "running"}
							class:bg-purple-500={activity === "generic"}
							style="width: {pct}%"
						></div>
					</div>
				</div>
			{/each}
		</div>

		<!-- Sleep Scores -->
		<div class="bg-white rounded-lg shadow p-6">
			<div
				class="text-sm font-medium text-gray-500 uppercase tracking-wide mb-4"
			>
				Sleep Scores
			</div>
			{#each overview.sleep_scores as sleep}
				<div
					class="flex justify-between items-center py-2 border-b border-gray-100 last:border-0"
				>
					<span class="text-sm text-gray-600">{sleep.date}</span>
					<span
						class="text-lg font-semibold"
						class:text-green-600={sleep.score >= 80}
						class:text-yellow-600={sleep.score >= 60 &&
							sleep.score < 80}
						class:text-red-600={sleep.score < 60}
					>
						{sleep.score}
					</span>
				</div>
			{/each}
		</div>
	</div>

	<!-- HRV Section -->
	<div class="bg-white rounded-lg shadow p-6 mb-8">
		<div
			class="text-sm font-medium text-gray-500 uppercase tracking-wide mb-4"
		>
			HRV Status
		</div>
		<div class="overflow-x-auto">
			<table class="min-w-full">
				<thead>
					<tr class="border-b border-gray-200">
						<th
							class="text-left py-2 text-sm font-medium text-gray-500"
							>Date</th
						>
						<th
							class="text-right py-2 text-sm font-medium text-gray-500"
							>Last Night Avg</th
						>
						<th
							class="text-right py-2 text-sm font-medium text-gray-500"
							>Weekly Avg</th
						>
						<th
							class="text-right py-2 text-sm font-medium text-gray-500"
							>Status</th
						>
					</tr>
				</thead>
				<tbody>
					{#each overview.hrv_summaries as hrv}
						<tr class="border-b border-gray-100">
							<td class="py-2 text-sm text-gray-700"
								>{hrv.date}</td
							>
							<td
								class="py-2 text-sm text-right text-gray-900 font-medium"
								>{hrv.last_night_average?.toFixed(0) ?? "-"} ms</td
							>
							<td class="py-2 text-sm text-right text-gray-600"
								>{hrv.weekly_average?.toFixed(0) ?? "-"} ms</td
							>
							<td class="py-2 text-sm text-right">
								<span
									class="px-2 py-1 rounded-full text-xs font-medium"
									class:bg-green-100={hrv.status.includes(
										"balanced",
									)}
									class:text-green-800={hrv.status.includes(
										"balanced",
									)}
									class:bg-yellow-100={hrv.status.includes(
										"low",
									)}
									class:text-yellow-800={hrv.status.includes(
										"low",
									)}
									class:bg-gray-100={!hrv.status.includes(
										"balanced",
									) && !hrv.status.includes("low")}
									class:text-gray-800={!hrv.status.includes(
										"balanced",
									) && !hrv.status.includes("low")}
								>
									{hrv.status}
								</span>
							</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
	</div>

	<!-- Data Summary -->
	<div class="bg-gray-100 rounded-lg p-4 text-sm text-gray-600">
		<strong>Data Summary:</strong> Analyzing {overview.total_days} days of Garmin
		Epix Gen 2 data with
		{formatNumber(overview.heart_rate.total_readings)} HR readings,
		{formatNumber(overview.stress.total_readings)} stress readings,
		{formatNumber(overview.spo2.total_readings)} SpO2 readings, and
		{formatNumber(overview.respiration.total_readings)} respiration readings.
	</div>
{:catch error}
	<div class="bg-red-50 border border-red-200 rounded-lg p-4">
		<p class="text-red-700">Error: {error.message}</p>
		<p class="text-sm text-red-600 mt-2">
			Make sure the backend is running at localhost:8000
		</p>
	</div>
{/await}
