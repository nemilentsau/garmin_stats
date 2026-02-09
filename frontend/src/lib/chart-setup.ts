import {
	Chart,
	LineController,
	LineElement,
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
	PointElement,
	LinearScale,
	CategoryScale,
	TimeScale,
	Filler,
	Tooltip,
	Legend
);

export { Chart };
