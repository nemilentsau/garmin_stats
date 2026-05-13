<script lang="ts">
	import type { AdherenceDayEntry } from '$lib/api';

	let {
		entries,
		rate,
		treatmentStart,
		treatmentEnd,
		currentDate
	}: {
		entries: AdherenceDayEntry[];
		rate: number;
		treatmentStart: string;
		treatmentEnd: string | null;
		currentDate: string;
	} = $props();

	function daysBetween(a: string, b: string): number {
		return Math.round(
			(new Date(b).getTime() - new Date(a).getTime()) / (1000 * 60 * 60 * 24)
		);
	}

	function fmtMonthDay(dateStr: string): string {
		const d = new Date(dateStr + 'T12:00:00');
		return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
	}

	function stateColor(state: string, isFuture: boolean): string {
		if (isFuture) return 'rgba(255,255,255,0.04)';
		if (state === 'full') return '#4CAF82';
		if (state === 'partial') return '#D4944C';
		if (state === 'missed') return '#E85D4A';
		return 'rgba(255,255,255,0.08)';
	}

	function stateLabel(state: string, isFuture: boolean, isToday: boolean): string {
		if (isFuture) return 'Upcoming';
		if (state === 'full') return 'Done';
		if (state === 'partial') return 'Partial';
		if (state === 'missed') return 'Missed';
		return isToday ? 'Not logged yet' : 'No data';
	}

	function addDays(start: string, n: number): string {
		const d = new Date(start + 'T12:00:00');
		d.setDate(d.getDate() + n);
		return d.toISOString().slice(0, 10);
	}

	const entriesByDate = $derived(
		new Map(entries.map((e) => [e.date, e] as const))
	);

	const plannedDays = $derived(
		treatmentEnd
			? Math.max(daysBetween(treatmentStart, treatmentEnd) + 1, 1)
			: Math.max(entries.length, 1)
	);

	const elapsedDays = $derived(
		Math.max(0, Math.min(daysBetween(treatmentStart, currentDate) + 1, plannedDays))
	);

	const currentDayNumber = $derived(Math.max(elapsedDays, 1));

	const cells = $derived(
		Array.from({ length: plannedDays }, (_, i) => {
			const date = addDays(treatmentStart, i);
			const entry = entriesByDate.get(date);
			const isFuture = date > currentDate;
			const isToday = date === currentDate;
			const state = entry?.state ?? 'unknown';
			return {
				date,
				dayIndex: i + 1,
				state,
				exposureScore: entry?.exposure_score ?? null,
				isFuture,
				isToday,
				color: stateColor(state, isFuture),
				label: stateLabel(state, isFuture, isToday)
			};
		})
	);

	const fullCount = $derived(
		cells.filter((c) => !c.isFuture && c.state === 'full').length
	);

	const partialCount = $derived(
		cells.filter((c) => !c.isFuture && c.state === 'partial').length
	);

	const missedCount = $derived(
		cells.filter((c) => !c.isFuture && c.state === 'missed').length
	);

	const elapsedHeadlinePct = $derived(
		elapsedDays > 0 ? Math.round((fullCount / elapsedDays) * 100) : 0
	);

	const startLabel = $derived(fmtMonthDay(treatmentStart));
	const endLabel = $derived(
		cells.length > 0 ? fmtMonthDay(cells[cells.length - 1].date) : ''
	);

	const adherenceTone = $derived(
		elapsedDays === 0
			? 'text-[#5e7282]'
			: elapsedHeadlinePct >= 70
				? 'text-[#4CAF82]'
				: elapsedHeadlinePct >= 50
					? 'text-[#D4944C]'
					: 'text-[#E85D4A]'
	);
</script>

<div class="rounded-xl border border-[rgba(255,255,255,0.05)] bg-[rgba(255,255,255,0.02)] px-5 py-4">
	<div class="mb-3 flex items-baseline justify-between gap-4">
		<div class="flex items-baseline gap-3">
			<h3 class="font-['DM_Mono',monospace] text-sm text-[#8a9baa]">Adherence</h3>
			<span class="font-['DM_Mono',monospace] text-[11px] text-[#5e7282]">
				Day {currentDayNumber} of {plannedDays}
			</span>
		</div>
		<div class="flex items-baseline gap-2">
			<span class="font-['DM_Mono',monospace] text-[11px] text-[#5e7282]">
				{fullCount}/{elapsedDays} fully adhered
			</span>
			<span class="text-base font-bold tabular-nums {adherenceTone}">
				{elapsedHeadlinePct}%
			</span>
		</div>
	</div>

	<div class="grid w-full gap-[3px]" style="grid-template-columns: repeat({cells.length}, minmax(0, 1fr));">
		{#each cells as cell}
			<div
				class="relative h-6 rounded-sm transition-opacity"
				class:ring-1={cell.isToday}
				class:ring-inset={cell.isToday}
				class:ring-white={cell.isToday}
				style="background: {cell.color};"
				title="Day {cell.dayIndex} · {fmtMonthDay(cell.date)} · {cell.label}{cell.exposureScore !== null && !cell.isFuture ? ` (${Math.round(cell.exposureScore * 100)}%)` : ''}"
			></div>
		{/each}
	</div>

	<div class="mt-2 flex items-center justify-between font-['DM_Mono',monospace] text-[10px] text-[#5e7282]">
		<span>{startLabel}</span>
		<span>{endLabel}</span>
	</div>

	<div class="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-[10px] text-[#5e7282]">
		<span class="inline-flex items-center gap-1.5">
			<span class="inline-block h-2 w-2 rounded-sm" style="background:#4CAF82"></span>
			Done {fullCount > 0 ? `(${fullCount})` : ''}
		</span>
		<span class="inline-flex items-center gap-1.5">
			<span class="inline-block h-2 w-2 rounded-sm" style="background:#D4944C"></span>
			Partial {partialCount > 0 ? `(${partialCount})` : ''}
		</span>
		<span class="inline-flex items-center gap-1.5">
			<span class="inline-block h-2 w-2 rounded-sm" style="background:#E85D4A"></span>
			Missed {missedCount > 0 ? `(${missedCount})` : ''}
		</span>
		<span class="inline-flex items-center gap-1.5">
			<span class="inline-block h-2 w-2 rounded-sm ring-1 ring-inset ring-white" style="background:rgba(255,255,255,0.08)"></span>
			Today
		</span>
		<span class="inline-flex items-center gap-1.5">
			<span class="inline-block h-2 w-2 rounded-sm" style="background:rgba(255,255,255,0.04)"></span>
			Upcoming
		</span>
	</div>
</div>
