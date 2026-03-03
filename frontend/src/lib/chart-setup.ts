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
