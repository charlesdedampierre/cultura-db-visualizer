# Cultura Visualizer

Interactive visualization of historical polities, individuals, and cities on a world map.

## Tech Stack

- **Frontend**: React + TypeScript + Vite + TailwindCSS + MapLibre GL + Recharts
- **Backend**: FastAPI + Supabase (PostgreSQL)

## Quick Start

### Backend

```bash
cd backend
pip install -r ../requirements.txt
uvicorn main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

The frontend runs on `http://localhost:5173` and the API on `http://localhost:8000`.

## API Endpoints

- `GET /api/health` - Health check
- `GET /api/polities` - List polities
- `GET /api/individuals` - List individuals
- `GET /api/cities` - List cities

## Data Pipeline

The database is built from source data through the following pipeline:

```
humans_clean.sqlite3  ──┐
                        ├──► extract_light_db.py ──► visualizer.sqlite3 ──► migrate_to_supabase.py ──► Supabase
cliopatria.db ──────────┘
```

### Source Databases

- **`data/humans_clean.sqlite3`** - Main database with individuals, cities, and polities
- **`cliopatria_data/processing/data/cliopatria.db`** - Polity hierarchy information

### Scripts

1. **`scripts/extract_light_db.py`** - Extracts and transforms data from source databases:
   - Polities with display_mode computed from hierarchy
   - Polity periods with simplified geometries (using Shapely)
   - Cities coordinates
   - Individuals (one row per individual-polity pair, impact dates rounded to 25-year buckets)
   - Pre-computed evolution_cache (counts per polity/year)
   - Pre-computed top_cities_cache (top 10 birth cities per polity)
   - Generates `frontend/public/evolution.json` and `frontend/public/occupations.json`

2. **`scripts/migrate_to_supabase.py`** - Migrates SQLite data to Supabase:
   - Uploads all tables in batches via Supabase REST API
   - Tables must be created first using Supabase CLI migrations

### Supabase Setup

Tables are defined in `supabase/migrations/` and pushed using:

```bash
supabase link --project-ref <project-ref>
supabase db push
```
