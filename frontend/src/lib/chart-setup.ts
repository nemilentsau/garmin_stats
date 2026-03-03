import {
	Chart,
	LineController,
	LineElement,
	BarController,
	BarElement,
	PointElement,
	LinearScale,
	CategoryScale,
	TimeScale,
	Filler,
	Tooltip,
	Legend
} from 'chart.js';
import 'chartjs-adapter-date-fns';
import annotationPlugin from 'chartjs-plugin-annotation';

Chart.register(
	LineController,
	LineElement,
	BarController,
	BarElement,
	PointElement,
	LinearScale,
	CategoryScale,
	TimeScale,
	Filler,
	Tooltip,
	Legend,
	annotationPlugin
);

export { Chart };

/** Standard dark-theme tooltip. Only borderColor varies per metric. */
export function chartTooltip(borderColor: string) {
	return { backgroundColor: '#1a2332', borderWidth: 1, borderColor, padding: 10, cornerRadius: 4 } as const;
}

/** Dark-theme scale grid/border/tick constants. */
export const DARK_GRID = { color: '#ffffff08' } as const;
export const DARK_GRID_Y = { color: '#ffffff06' } as const;
export const DARK_BORDER = { color: '#ffffff10' } as const;
export const DARK_TICK = { color: '#6b7d8e' } as const;
