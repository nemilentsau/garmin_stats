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
	Legend
);

export { Chart };
