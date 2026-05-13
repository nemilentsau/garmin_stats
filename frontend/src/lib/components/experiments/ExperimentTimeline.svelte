<script lang="ts">
	let {
		baselineStart,
		baselineEnd,
		treatmentStart,
		treatmentEnd,
		currentDate
	}: {
		baselineStart: string;
		baselineEnd: string;
		treatmentStart: string;
		treatmentEnd: string | null;
		currentDate: string;
	} = $props();

	function daysBetween(a: string, b: string): number {
		return Math.round(
			(new Date(b).getTime() - new Date(a).getTime()) / (1000 * 60 * 60 * 24)
		);
	}

	const baselineDays = $derived(daysBetween(baselineStart, baselineEnd) + 1);
	const isOngoing = $derived(!treatmentEnd || treatmentEnd > currentDate);
	const plannedTreatmentDays = $derived(
		treatmentEnd
			? daysBetween(treatmentStart, treatmentEnd) + 1
			: Math.max(daysBetween(treatmentStart, currentDate) + 1, 1)
	);
	const elapsedTreatmentDays = $derived(
		Math.max(0, Math.min(daysBetween(treatmentStart, currentDate) + 1, plannedTreatmentDays))
	);
	const totalDays = $derived(baselineDays + plannedTreatmentDays);
	const baselinePct = $derived(Math.round((baselineDays / totalDays) * 100));
	const treatmentPct = $derived(100 - baselinePct);
	const treatmentProgress = $derived(
		isOngoing ? Math.round((elapsedTreatmentDays / plannedTreatmentDays) * 100) : 100
	);
</script>

<div class="space-y-2">
	<div class="flex h-3 w-full overflow-hidden rounded-full bg-[rgba(255,255,255,0.04)]">
		<div
			class="h-full rounded-l-full"
			style="width: {baselinePct}%; background: rgba(94, 114, 130, 0.5);"
		></div>
		<div
			class="h-full rounded-r-full"
			style="width: {treatmentPct}%; background: linear-gradient(90deg, rgba(91,181,166,0.4), rgba(91,181,166,0.7) {treatmentProgress}%, rgba(91,181,166,0.15) {treatmentProgress}%);"
		></div>
	</div>
	<div class="flex justify-between text-[11px] font-['DM_Mono',monospace] text-[#5e7282]">
		<span>Baseline {baselineDays}d</span>
		<span>
			Treatment {elapsedTreatmentDays}{#if isOngoing}/{plannedTreatmentDays}{/if}d
		</span>
	</div>
</div>
