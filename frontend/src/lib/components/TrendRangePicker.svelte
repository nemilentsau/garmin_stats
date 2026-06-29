<script lang="ts">
	import { TREND_RANGES, type TrendRange } from '$lib/trend-range';
	import SegmentedPicker from './SegmentedPicker.svelte';

	let { value = $bindable<TrendRange>('3M') }: { value: TrendRange } = $props();
</script>

<SegmentedPicker options={TREND_RANGES} {value} onchange={(r) => (value = r)} />
