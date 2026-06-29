<script lang="ts">
	import { HRV_BASELINE_WINDOWS, type HrvBaselineWindow } from '$lib/hrv-baseline';
	import SegmentedPicker from './SegmentedPicker.svelte';

	let {
		value,
		onchange,
		disabled = false
	}: { value: HrvBaselineWindow; onchange: (w: HrvBaselineWindow) => void; disabled?: boolean } = $props();
</script>

<SegmentedPicker
	options={HRV_BASELINE_WINDOWS}
	{value}
	{onchange}
	{disabled}
	label={(w) => `${w}d`}
/>
