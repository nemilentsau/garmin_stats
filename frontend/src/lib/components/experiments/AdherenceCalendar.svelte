<script lang="ts">
	import type { AdherenceDayEntry } from '$lib/api';
	import { addDays, calendarDayDiff, parseIsoDate } from '$lib/date';

	type AdherenceState = AdherenceDayEntry['state'];

	let {
		entries,
		treatmentStart,
		treatmentEnd,
		currentDate
	}: {
		entries: AdherenceDayEntry[];
		treatmentStart: string;
		treatmentEnd: string | null;
		currentDate: string;
	} = $props();

	const monthDayFormat = new Intl.DateTimeFormat(undefined, {
		month: 'short',
		day: 'numeric'
	});
	function fmtMonthDay(dateStr: string): string {
		return monthDayFormat.format(parseIsoDate(dateStr));
	}

	const STATE_VISUAL: Record<AdherenceState, { color: string; label: string }> = {
		full: { color: '#4CAF82', label: 'Done' },
		partial: { color: '#D4944C', label: 'Partial' },
		missed: { color: '#E85D4A', label: 'Missed' },
		unknown: { color: 'rgba(255,255,255,0.08)', label: 'No data' }
	};

	function cellVisual(
		state: AdherenceState,
		isFuture: boolean,
		isToday: boolean
	): { color: string; label: string } {
		if (isFuture) return { color: 'rgba(255,255,255,0.04)', label: 'Upcoming' };
		if (state === 'unknown' && isToday) {
			return { color: STATE_VISUAL.unknown.color, label: 'Not logged yet' };
		}
		return STATE_VISUAL[state];
	}

	const entriesByDate = $derived(
		new Map(entries.map((e) => [e.date, e] as const))
	);

	const plannedDays = $derived(
		treatmentEnd
			? Math.max(calendarDayDiff(treatmentStart, treatmentEnd) + 1, 1)
			: Math.max(entries.length, 1)
	);

	const elapsedDays = $derived(
		Math.max(0, Math.min(calendarDayDiff(treatmentStart, currentDate) + 1, plannedDays))
	);

	const cells = $derived(
		Array.from({ length: plannedDays }, (_, i) => {
			const date = addDays(treatmentStart, i);
			const entry = entriesByDate.get(date);
			const isFuture = date > currentDate;
			const isToday = date === currentDate;
			const state: AdherenceState = entry?.state ?? 'unknown';
			const visual = cellVisual(state, isFuture, isToday);
			return {
				date,
				dateLabel: fmtMonthDay(date),
				dayIndex: i + 1,
				state,
				exposureScore: entry?.exposure_score ?? null,
				isFuture,
				isToday,
				color: visual.color,
				label: visual.label
			};
		})
	);

	const counts = $derived(
		cells.reduce(
			(acc, c) => {
				if (!c.isFuture) acc[c.state] += 1;
				return acc;
			},
			{ full: 0, partial: 0, missed: 0, unknown: 0 } as Record<AdherenceState, number>
		)
	);

	const elapsedHeadlinePct = $derived(
		elapsedDays > 0 ? Math.round((counts.full / elapsedDays) * 100) : 0
	);

	const startLabel = $derived(fmtMonthDay(treatmentStart));
	const endLabel = $derived(cells.length > 0 ? cells[cells.length - 1].dateLabel : '');

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
				Day {elapsedDays} of {plannedDays}
			</span>
		</div>
		<div class="flex items-baseline gap-2">
			<span class="font-['DM_Mono',monospace] text-[11px] text-[#5e7282]">
				{counts.full}/{elapsedDays} fully adhered
			</span>
			<span class="text-base font-bold tabular-nums {adherenceTone}">
				{elapsedHeadlinePct}%
			</span>
		</div>
	</div>

	<div
		class="grid w-full gap-[3px]"
		style="grid-template-columns: repeat({cells.length}, minmax(0, 1fr));"
	>
		{#each cells as cell}
			<div
				class="relative h-6 rounded-sm transition-opacity"
				class:ring-1={cell.isToday}
				class:ring-inset={cell.isToday}
				class:ring-white={cell.isToday}
				style="background: {cell.color};"
				title="Day {cell.dayIndex} · {cell.dateLabel} · {cell.label}{cell.exposureScore !== null && !cell.isFuture ? ` (${Math.round(cell.exposureScore * 100)}%)` : ''}"
			></div>
		{/each}
	</div>

	<div class="mt-2 flex items-center justify-between font-['DM_Mono',monospace] text-[10px] text-[#5e7282]">
		<span>{startLabel}</span>
		<span>{endLabel}</span>
	</div>

	<div class="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-[10px] text-[#5e7282]">
		<span class="inline-flex items-center gap-1.5">
			<span class="inline-block h-2 w-2 rounded-sm" style="background:{STATE_VISUAL.full.color}"></span>
			Done {counts.full > 0 ? `(${counts.full})` : ''}
		</span>
		<span class="inline-flex items-center gap-1.5">
			<span class="inline-block h-2 w-2 rounded-sm" style="background:{STATE_VISUAL.partial.color}"></span>
			Partial {counts.partial > 0 ? `(${counts.partial})` : ''}
		</span>
		<span class="inline-flex items-center gap-1.5">
			<span class="inline-block h-2 w-2 rounded-sm" style="background:{STATE_VISUAL.missed.color}"></span>
			Missed {counts.missed > 0 ? `(${counts.missed})` : ''}
		</span>
		<span class="inline-flex items-center gap-1.5">
			<span class="inline-block h-2 w-2 rounded-sm ring-1 ring-inset ring-white" style="background:{STATE_VISUAL.unknown.color}"></span>
			Today
		</span>
		<span class="inline-flex items-center gap-1.5">
			<span class="inline-block h-2 w-2 rounded-sm" style="background:rgba(255,255,255,0.04)"></span>
			Upcoming
		</span>
	</div>
</div>
