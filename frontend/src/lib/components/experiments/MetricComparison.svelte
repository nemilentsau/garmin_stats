<script lang="ts">
	import type { MetricAnalysis, MetricLagResult } from '$lib/api';
	import ConfidenceBadge from './ConfidenceBadge.svelte';

	let { metric }: { metric: MetricAnalysis } = $props();

	let selectedLagOverride: number | null = $state(null);
	const selectedLag = $derived(selectedLagOverride ?? metric.best_lag);

	const currentResult = $derived(
		metric.lag_results.find((r) => r.lag_days === selectedLag) ?? metric.best_result
	);

	function fmtPct(v: number): string {
		const sign = v > 0 ? '+' : '';
		return `${sign}${v.toFixed(1)}%`;
	}

	function fmtVal(v: number): string {
		return v.toFixed(1);
	}

	function napColor(interp: string): string {
		if (interp === 'large') return '#4CAF82';
		if (interp === 'medium') return '#5BB5A6';
		if (interp === 'weak') return '#D4944C';
		return '#8e9eaa';
	}

	function pColor(p: number): string {
		if (p < 0.01) return '#4CAF82';
		if (p < 0.05) return '#5BB5A6';
		if (p < 0.10) return '#D4944C';
		return '#8e9eaa';
	}

	function effectLabel(g: number): string {
		const abs = Math.abs(g);
		if (abs >= 0.8) return 'large';
		if (abs >= 0.5) return 'medium';
		if (abs >= 0.2) return 'small';
		return 'negligible';
	}

	const r = $derived(currentResult);
</script>

<div class="rounded-xl border border-[rgba(255,255,255,0.05)] bg-[rgba(255,255,255,0.02)] p-5">
	<div class="mb-4 flex items-center justify-between">
		<h3 class="font-['DM_Mono',monospace] text-sm text-[#8a9baa]">
			{metric.path}
		</h3>
		{#if r.direction_correct}
			<span class="text-xs text-[#4CAF82]">correct direction</span>
		{:else}
			<span class="text-xs text-[#E85D4A]">wrong direction</span>
		{/if}
	</div>

	<!-- Baseline vs Treatment comparison -->
	<div class="mb-5 grid grid-cols-3 gap-4 text-center">
		<div>
			<div class="text-[11px] uppercase tracking-wider text-[#5e7282]">Baseline</div>
			<div class="mt-1 text-xl font-bold text-[#8a9baa]">{fmtVal(r.baseline_mean)}</div>
			<div class="text-[10px] text-[#4a5c6a]">{r.baseline_n}d, SD {fmtVal(r.baseline_sd)}</div>
		</div>
		<div>
			<div class="text-[11px] uppercase tracking-wider text-[#5e7282]">Delta</div>
			<div
				class="mt-1 text-xl font-bold"
				class:text-[#4CAF82]={r.direction_correct}
				class:text-[#E85D4A]={!r.direction_correct}
			>
				{fmtPct(r.delta_pct)}
			</div>
			<div class="text-[10px] text-[#4a5c6a]">{r.delta_abs > 0 ? '+' : ''}{fmtVal(r.delta_abs)} abs</div>
		</div>
		<div>
			<div class="text-[11px] uppercase tracking-wider text-[#5e7282]">Treatment</div>
			<div class="mt-1 text-xl font-bold text-[#e8f0f5]">{fmtVal(r.treatment_mean)}</div>
			<div class="text-[10px] text-[#4a5c6a]">{r.treatment_n}d, SD {fmtVal(r.treatment_sd)}</div>
		</div>
	</div>

	<!-- Statistical results -->
	<div class="grid grid-cols-2 gap-3 sm:grid-cols-4">
		<div class="rounded-lg bg-[rgba(255,255,255,0.02)] p-3">
			<div class="text-[10px] uppercase tracking-wider text-[#5e7282]">NAP</div>
			<div class="mt-0.5 text-lg font-bold" style="color: {napColor(r.nap_interpretation)}">
				{r.nap.toFixed(2)}
			</div>
			<div class="text-[10px]" style="color: {napColor(r.nap_interpretation)}">
				{r.nap_interpretation}
			</div>
		</div>
		<div class="rounded-lg bg-[rgba(255,255,255,0.02)] p-3">
			<div class="text-[10px] uppercase tracking-wider text-[#5e7282]">Hedges' g</div>
			<div class="mt-0.5 text-lg font-bold text-[#e8f0f5]">
				{r.hedges_g.toFixed(2)}
			</div>
			<div class="text-[10px] text-[#5e7282]">{effectLabel(r.hedges_g)}</div>
		</div>
		<div class="rounded-lg bg-[rgba(255,255,255,0.02)] p-3">
			<div class="text-[10px] uppercase tracking-wider text-[#5e7282]">p (perm)</div>
			<div class="mt-0.5 text-lg font-bold" style="color: {pColor(r.p_value_permutation)}">
				{r.p_value_permutation < 0.001 ? '<.001' : r.p_value_permutation.toFixed(3)}
			</div>
			<div class="text-[10px] text-[#5e7282]">permutation</div>
		</div>
		<div class="rounded-lg bg-[rgba(255,255,255,0.02)] p-3">
			<div class="text-[10px] uppercase tracking-wider text-[#5e7282]">p (Welch)</div>
			<div class="mt-0.5 text-lg font-bold" style="color: {pColor(r.p_value_welch)}">
				{r.p_value_welch < 0.001 ? '<.001' : r.p_value_welch.toFixed(3)}
			</div>
			<div class="text-[10px] text-[#5e7282]">t-test</div>
		</div>
	</div>

	<!-- Diagnostics -->
	{#if r.baseline_trend_p < 0.05 || r.autocorrelation_lag1_baseline > 0.3}
		<div class="mt-3 space-y-1 text-[11px] text-[#D4944C]">
			{#if r.baseline_trend_p < 0.05}
				<div>Baseline had significant trend (slope={r.baseline_trend_slope.toFixed(3)}, p={r.baseline_trend_p.toFixed(3)})</div>
			{/if}
			{#if r.autocorrelation_lag1_baseline > 0.3}
				<div>Baseline autocorrelation: r={r.autocorrelation_lag1_baseline.toFixed(2)} — significance may be inflated</div>
			{/if}
		</div>
	{/if}

	<!-- Lag selector -->
	{#if metric.lag_results.length > 1}
		<div class="mt-4 flex items-center gap-2">
			<span class="text-[10px] uppercase tracking-wider text-[#5e7282]">Lag offset:</span>
			{#each metric.lag_results as lr}
				<button
					class="rounded-md px-2.5 py-1 text-[11px] font-medium transition-colors"
					class:bg-[rgba(91,181,166,0.2)]={selectedLag === lr.lag_days}
					class:text-[#5BB5A6]={selectedLag === lr.lag_days}
					class:bg-[rgba(255,255,255,0.04)]={selectedLag !== lr.lag_days}
					class:text-[#5e7282]={selectedLag !== lr.lag_days}
					onclick={() => (selectedLagOverride = lr.lag_days)}
				>
					{lr.lag_days}d
					{#if lr.lag_days === metric.best_lag}*{/if}
				</button>
			{/each}
		</div>
	{/if}
</div>
