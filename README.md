# Garmin Stats

Personal health data analysis tool for Garmin Epix Gen 2 watch data.

## Project Vision

Build a comprehensive tool to explore, analyze, and visualize health metrics from Garmin FIT file exports. The goal is to gain insights into personal health trends beyond what the Garmin Connect app provides.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                          Frontend                               │
│                   Svelte 5 + Runes + Tailwind                   │
│         Dashboard, Charts, Trends, Data Exploration             │
│                    http://localhost:5173                        │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Python Backend                             │
│                    FastAPI REST API Server                      │
│         Data Processing, Analytics, Export Endpoints            │
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
│   └── ...
├── 2026-01-15/
│   └── ...
```

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /api/overview` | Overview statistics across all data |
| `GET /api/days` | List available days of data |
| `GET /api/days/{date}` | Summary for a specific day |
| `GET /api/wellness?date=YYYY-MM-DD` | Wellness data (HR, stress, SpO2, respiration) |
| `GET /api/sleep?date=YYYY-MM-DD` | Sleep data (stages, assessment scores) |
| `GET /api/hrv?date=YYYY-MM-DD` | HRV data (values, summaries) |

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
│   │   ├── main.py      # FastAPI application
│   │   └── parser.py    # FIT file parsing service
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── lib/
│   │   │   └── api.ts   # API client
│   │   └── routes/
│   │       └── +page.svelte  # Dashboard
│   └── package.json
├── data/                # FIT files (gitignored)
├── explore_fit_files.py # CLI exploration tool
├── FINDINGS.md          # Data analysis findings
└── README.md
```

## Roadmap

- [x] Phase 1: Data Exploration - FIT file parsing with official SDK
- [x] Phase 2: Basic App - FastAPI backend + Svelte dashboard
- [ ] Phase 3: Time Series - Charts for HR, stress, activity over time
- [ ] Phase 4: Database - SQLite storage for parsed data
- [ ] Phase 5: Advanced Analytics - Trends, correlations, anomaly detection

## Data Privacy

The `data/` directory is gitignored to keep personal health data private. Never commit FIT files or exported health data to version control.

## License

Private project - not for distribution.
