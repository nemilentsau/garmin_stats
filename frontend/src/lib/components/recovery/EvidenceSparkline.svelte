<script lang="ts">
	import type { DashboardOverview } from '$lib/api';

	let {
		points,
		color,
		width = 96,
		height = 26
	}: {
		points: DashboardOverview['evidence'][number]['sparkline'];
		color: string;
		width?: number;
		height?: number;
	} = $props();

	// Self-normalized to this metric's own recent range so the SHAPE is legible
	// (metrics have different units; cross-row comparison lives in the Δz column).
	const path = $derived.by(() => {
		const vals = points.map((p) => p.value).filter((v): v is number => v != null);
		if (vals.length < 2) return null;
		const lo = Math.min(...vals);
		const hi = Math.max(...vals);
		const span = hi - lo || 1;
		const pad = 3;
		const innerH = height - pad * 2;
		const n = points.length;
		let d = '';
		let started = false;
		points.forEach((p, i) => {
			if (p.value == null) {
				started = false;
				return;
			}
			const x = (i / (n - 1)) * width;
			const y = pad + innerH - ((p.value - lo) / span) * innerH;
			d += `${started ? 'L' : 'M'}${x.toFixed(1)},${y.toFixed(1)} `;
			started = true;
		});
		const last = points[points.length - 1];
		const lastDot =
			last.value == null ? null : { x: width, y: pad + innerH - ((last.value - lo) / span) * innerH };
		return { d: d.trim(), lastDot };
	});
</script>

{#if path}
	<svg {width} {height} viewBox="0 0 {width} {height}" class="spark" aria-hidden="true">
		<path d={path.d} fill="none" stroke={color} stroke-width="1.25" stroke-opacity="0.8" />
		{#if path.lastDot}
			<circle cx={path.lastDot.x} cy={path.lastDot.y} r="1.8" fill={color} />
		{/if}
	</svg>
{:else}
	<span class="empty">—</span>
{/if}

<style>
	.spark {
		display: block;
	}
	.empty {
		color: #5e7282;
		font-size: 12px;
	}
</style>
