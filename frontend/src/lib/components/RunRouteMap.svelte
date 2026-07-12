<script lang="ts">
	/**
	 * GPS route map for the run detail page. Leaflet + OpenStreetMap tiles, dark-filtered to
	 * match the app's muted surfaces. The route line is built as per-segment polylines colored
	 * by binning the PROVIDED pace values into 5 quantile bins (quintiles) of that run's own
	 * pace distribution — a display mapping of already-computed values (client-computed order
	 * statistics from `tightScale` in chart-scale.ts, used purely for display calibration, never
	 * displayed as data), never a statistical transform. Quantile (equal-population) edges are
	 * used rather than equal-width min/max bins because urban runs carry extreme stop/light
	 * outliers (this route: 6.6-27.1 min/mi) that would otherwise pack ~99% of segments into
	 * a single bin and make the coloring invisible — quantiles keep the color spread meaningful
	 * across the run's actual pace variation. Segments with no pace on either endpoint draw
	 * neutral gray rather than being dropped, so GPS-but-no-pace stretches (e.g. paused/stopped)
	 * still read as part of the route. GPS gaps (consecutive null lat/lon indices) are never
	 * bridged; segments terminate at the gap and resume after it.
	 *
	 * Leaflet touches `window`/`document` at import time, so the library itself is loaded with a
	 * dynamic `import()` inside `onMount` — never at module scope — to stay SSR-safe. The CSS is
	 * inert and can be imported statically.
	 */
	import { onMount, onDestroy } from 'svelte';
	import type { Map as LeafletMap } from 'leaflet';
	import 'leaflet/dist/leaflet.css';
	import { COLORS } from '$lib/colors';

	let {
		lat,
		lon,
		pace
	}: {
		lat: (number | null)[];
		lon: (number | null)[];
		pace: (number | null)[];
	} = $props();

	let container: HTMLDivElement;
	let map: LeafletMap | null = null;

	// Fastest → slowest, warm → cool. Reuses the app's existing heart-rate red and pace blue at
	// the two ends so the map reads as part of the same color system as the charts below it.
	const PACE_BIN_COLORS = [COLORS.heartRate, COLORS.paceQuantile2, COLORS.stress, COLORS.paceQuantile4, COLORS.pace] as const;
	const NULL_PACE_COLOR = COLORS.baseline;
	const START_COLOR = '#4CAF82';
	const END_COLOR = '#E85D4A';

	type RoutePoint = { lat: number; lon: number; pace: number | null };
	type RouteSegment = { points: RoutePoint[] };

	/** Build contiguous route segments, never bridging GPS gaps (null lat/lon indices). */
	function buildSegments(): RouteSegment[] {
		const segments: RouteSegment[] = [];
		let currentSegment: RoutePoint[] = [];

		for (let i = 0; i < lat.length; i++) {
			const la = lat[i];
			const lo = lon[i];

			if (la == null || lo == null) {
				// Gap encountered: finalize current segment if it has points
				if (currentSegment.length > 0) {
					segments.push({ points: currentSegment });
					currentSegment = [];
				}
			} else {
				// Valid coordinate: add to current segment
				currentSegment.push({ lat: la, lon: lo, pace: pace[i] ?? null });
			}
		}

		// Finalize any remaining segment
		if (currentSegment.length > 0) {
			segments.push({ points: currentSegment });
		}

		return segments;
	}

	/** Interior quintile edges (4 cut points for 5 bins) of a sorted value array. */
	function quantileEdges(sorted: number[], binCount: number): number[] {
		const edges: number[] = [];
		for (let k = 1; k < binCount; k++) {
			const pos = (k / binCount) * (sorted.length - 1);
			const lo = Math.floor(pos);
			const hi = Math.ceil(pos);
			const frac = pos - lo;
			edges.push(sorted[lo] + (sorted[hi] - sorted[lo]) * frac);
		}
		return edges;
	}

	/** Bin a pace value against precomputed quantile edges. */
	function binColor(value: number, edges: number[]): string {
		let idx = 0;
		for (const edge of edges) {
			if (value > edge) idx++;
		}
		return PACE_BIN_COLORS[Math.min(idx, PACE_BIN_COLORS.length - 1)];
	}

	onMount(() => {
		let cancelled = false;

		(async () => {
			const segments = buildSegments();
			// Collect all valid points across all segments for markers and bounds
			const allPoints: RoutePoint[] = [];
			for (const seg of segments) {
				allPoints.push(...seg.points);
			}
			if (allPoints.length < 2) return; // no usable GPS trace — leave the panel empty

			const L = await import('leaflet');
			if (cancelled || !container) return;

			const leafletMap = L.map(container, { preferCanvas: true });

			L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
				attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
				maxZoom: 19,
				className: 'run-route-tiles'
			}).addTo(leafletMap);

			const sortedPace = pace.filter((v): v is number => v != null).sort((x, y) => x - y);
			const edges = sortedPace.length ? quantileEdges(sortedPace, PACE_BIN_COLORS.length) : [];

			// Draw each segment independently, never bridging gaps
			for (const segment of segments) {
				if (segment.points.length < 2) continue; // skip degenerate segments
				const points = segment.points;
				for (let i = 0; i < points.length - 1; i++) {
					const a = points[i];
					const b = points[i + 1];
					const segPace = a.pace != null && b.pace != null ? (a.pace + b.pace) / 2 : (a.pace ?? b.pace);
					const color = segPace != null ? binColor(segPace, edges) : NULL_PACE_COLOR;
					L.polyline(
						[
							[a.lat, a.lon],
							[b.lat, b.lon]
						],
						{ color, weight: 4, opacity: 0.9, lineCap: 'round' }
					).addTo(leafletMap);
				}
			}

			const start = allPoints[0];
			const end = allPoints[allPoints.length - 1];
			L.circleMarker([start.lat, start.lon], {
				radius: 7,
				color: '#e8f0f5',
				weight: 2,
				fillColor: START_COLOR,
				fillOpacity: 1
			}).addTo(leafletMap);
			L.circleMarker([end.lat, end.lon], {
				radius: 7,
				color: '#e8f0f5',
				weight: 2,
				fillColor: END_COLOR,
				fillOpacity: 1
			}).addTo(leafletMap);

			leafletMap.fitBounds(
				L.latLngBounds(allPoints.map((p) => [p.lat, p.lon] as [number, number])),
				{ padding: [24, 24] }
			);

			map = leafletMap;
		})();

		return () => {
			cancelled = true;
		};
	});

	onDestroy(() => {
		map?.remove();
		map = null;
	});
</script>

<div class="run-route-map" bind:this={container}></div>

<style>
	.run-route-map {
		width: 100%;
		height: 100%;
		background: #0d1520;
	}

	/* Dark-theme tile treatment: invert + counter-rotate hue back toward the source colors,
	   desaturate and dim slightly so the route line stays the clear figure against the tiles. */
	:global(.run-route-map .run-route-tiles) {
		filter: grayscale(0.25) invert(0.92) brightness(0.85) contrast(0.9) hue-rotate(180deg);
	}

	:global(.run-route-map .leaflet-control-attribution) {
		background: rgba(13, 21, 32, 0.75);
		color: #6b7d8e;
	}
	:global(.run-route-map .leaflet-control-attribution a) {
		color: #8a9baa;
	}
	:global(.run-route-map .leaflet-control-zoom a) {
		background: rgba(13, 21, 32, 0.85);
		color: #c3d3dd;
		border-color: rgba(255, 255, 255, 0.1);
	}
	:global(.run-route-map .leaflet-control-zoom a:hover) {
		background: rgba(13, 21, 32, 1);
		color: #e8f0f5;
	}
</style>
