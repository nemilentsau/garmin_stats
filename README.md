# Garmin Stats

Personal health data analysis tool for Garmin Epix Gen 2 watch data.

## Project Vision

Build a comprehensive tool to explore, analyze, and visualize health metrics from Garmin FIT file exports. The goal is to gain insights into personal health trends beyond what the Garmin Connect app provides.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                          Frontend                               │
│              Svelte 5 + Runes + Tailwind + Chart.js             │
│       Dashboard, Trend Charts, Metric Subtabs, Intraday         │
│                    http://localhost:5173                        │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Python Backend                             │
│                    FastAPI REST API Server                      │
│         Data Processing, Daily Aggregates, Export               │
│                    http://localhost:8000                        │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Data Ingestion Layer                       │
│              Official Garmin FIT SDK (garmin-fit-sdk)           │
│           Raw FIT files → Structured data models                │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                       Raw Data (gitignored)                     │
│                    Garmin FIT file exports                      │
│                      data/YYYY-MM-DD/*.fit                      │
└─────────────────────────────────────────────────────────────────┘
```

## Quick Start

### Prerequisites

- Python 3.12+
- Node.js 20+
- [uv](https://github.com/astral-sh/uv) for Python environment management

### 1. Backend Setup

```bash
# From project root
cd backend
uv venv
uv pip install -r requirements.txt

# Run the API server
uv run uvicorn app.main:app --reload
```

API will be available at http://localhost:8000

### 2. Frontend Setup

```bash
# From project root
cd frontend
npm install

# Run the dev server
npm run dev
```

Dashboard will be available at http://localhost:5173

### 3. Add Your Data

Export FIT files from Garmin Connect and place them in date-based directories:

```
data/
├── 2026-01-14/
│   ├── 398995029297_METRICS.fit
│   ├── 398995072007_WELLNESS.fit
│   ├── 398995072007_SKIN_TEMP.fit
│   └── ...
├── 2026-01-15/
│   └── ...
```

## Frontend Pages

| Route | Description |
|-------|-------------|
| `/` | Dashboard — 7 trend chart panels (HR, Stress, SpO2, Respiration, HRV, Sleep, Skin Temp) |
| `/heart-rate` | Heart rate detail — trend + intraday view, resting HR tracking |
| `/hrv` | HRV detail — nightly/weekly averages, balanced status tracking |
| `/respiration` | Respiration detail — trend + intraday, min/max bands |
| `/skin-temp` | Skin temperature — deviation from baseline, 7-day smoothed trend |
| `/pulse-ox` | Pulse Ox (SpO2) — daily avg + min tracking, low-value flagging |

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /api/daily-aggregates` | Per-day stats for all metrics (dashboard data source) |
| `GET /api/overview` | Overview statistics across all data |
| `GET /api/days` | List available days of data |
| `GET /api/days/{date}` | Summary for a specific day |
| `GET /api/wellness?date=YYYY-MM-DD` | Wellness data (HR, stress, SpO2, respiration) |
| `GET /api/sleep?date=YYYY-MM-DD` | Sleep data (stages, assessment scores) |
| `GET /api/hrv?date=YYYY-MM-DD` | HRV data (values, summaries) |
| `GET /api/skin-temp?date=YYYY-MM-DD` | Skin temperature data |

## Data Explorer Script

For command-line exploration of FIT files:

```bash
# From project root
uv run python explore_fit_files.py --summary-only
uv run python explore_fit_files.py --by-day
uv run python explore_fit_files.py --type WELLNESS
```

## Project Structure

```
garmin_stats/
├── backend/
│   ├── app/
│   │   ├── main.py          # FastAPI application + endpoints
│   │   └── parser.py        # FIT file parsing (wellness, sleep, HRV, skin temp, aggregates)
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── lib/
│   │   │   ├── api.ts              # Typed API client
│   │   │   ├── chart-setup.ts      # Chart.js registration + date adapter
│   │   │   └── components/
│   │   │       ├── LineChart.svelte       # Chart.js line chart wrapper
│   │   │       ├── StatCard.svelte        # Summary stat card
│   │   │       ├── MetricDefinition.svelte # Collapsible info box
│   │   │       └── DateSelector.svelte    # Day picker dropdown
│   │   └── routes/
│   │       ├── +layout.svelte      # App shell + tab navigation
│   │       ├── +page.svelte        # Dashboard with trend charts
│   │       ├── heart-rate/+page.svelte
│   │       ├── hrv/+page.svelte
│   │       ├── respiration/+page.svelte
│   │       ├── skin-temp/+page.svelte
│   │       └── pulse-ox/+page.svelte
│   └── package.json
├── data/                    # FIT files (gitignored)
├── explore_fit_files.py     # CLI exploration tool
├── CLAUDE.md                # Project rules + gotchas for AI assistants
├── FINDINGS.md              # Data analysis findings
└── README.md
```

## Roadmap

- [x] Phase 1: Data Exploration — FIT file parsing with official SDK
- [x] Phase 2: Basic App — FastAPI backend + Svelte dashboard
- [x] Phase 3: Time Series — Trend charts for all metrics, metric subtab pages with intraday views
- [ ] Phase 4: Database — SQLite storage for parsed data
- [ ] Phase 5: Advanced Analytics — Trends, correlations, anomaly detection

## Data Privacy

The `data/` directory is gitignored to keep personal health data private. Never commit FIT files or exported health data to version control.

## License

Private project - not for distribution.
