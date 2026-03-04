"""Create tables in Supabase."""

import os
import httpx
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_Project_URL")
SUPABASE_KEY = os.getenv("SUPABASE_API_KEY")

SQL_SCHEMA = """
CREATE TABLE IF NOT EXISTS polities (
    id BIGINT PRIMARY KEY,
    name TEXT,
    type TEXT,
    wikipedia_url TEXT,
    wikidata_id TEXT,
    individuals_count INTEGER,
    display_mode TEXT DEFAULT 'both'
);

CREATE TABLE IF NOT EXISTS polity_periods (
    id BIGINT PRIMARY KEY,
    polity_id BIGINT REFERENCES polities(id),
    polity_name TEXT,
    from_year INTEGER,
    to_year INTEGER,
    area REAL,
    geometry TEXT
);

CREATE TABLE IF NOT EXISTS cities (
    id TEXT PRIMARY KEY,
    name_en TEXT,
    lat REAL,
    lon REAL,
    iso_country_name TEXT
);

CREATE TABLE IF NOT EXISTS individuals_light (
    wikidata_id TEXT,
    name_en TEXT,
    occupations_en TEXT,
    sitelinks_count INTEGER,
    impact_date INTEGER,
    impact_date_raw INTEGER,
    polity_id BIGINT REFERENCES polities(id),
    birthcity_id TEXT,
    deathcity_id TEXT,
    PRIMARY KEY (wikidata_id, polity_id)
);

CREATE TABLE IF NOT EXISTS evolution_cache (
    polity_id BIGINT REFERENCES polities(id),
    year INTEGER,
    count INTEGER,
    PRIMARY KEY (polity_id, year)
);

CREATE TABLE IF NOT EXISTS top_cities_cache (
    polity_id BIGINT REFERENCES polities(id),
    city_id TEXT,
    city_name TEXT,
    lat REAL,
    lon REAL,
    individual_count INTEGER,
    PRIMARY KEY (polity_id, city_id)
);

CREATE INDEX IF NOT EXISTS idx_pp_polity ON polity_periods(polity_id);
CREATE INDEX IF NOT EXISTS idx_pp_years ON polity_periods(from_year, to_year);
CREATE INDEX IF NOT EXISTS idx_il_polity ON individuals_light(polity_id);
CREATE INDEX IF NOT EXISTS idx_il_polity_sitelinks ON individuals_light(polity_id, sitelinks_count DESC);
CREATE INDEX IF NOT EXISTS idx_il_polity_impact ON individuals_light(polity_id, impact_date);
"""

def create_tables():
    """Create tables using Supabase SQL API."""
    print(f"Supabase URL: {SUPABASE_URL}")

    # Try using the SQL endpoint (requires service_role key)
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
    }

    # Execute each statement separately
    statements = [s.strip() for s in SQL_SCHEMA.split(';') if s.strip()]

    for i, stmt in enumerate(statements, 1):
        print(f"\n[{i}/{len(statements)}] Executing: {stmt[:50]}...")

        response = httpx.post(
            f"{SUPABASE_URL}/rest/v1/rpc/exec_sql",
            headers=headers,
            json={"query": stmt},
            timeout=30,
        )

        if response.status_code == 200:
            print(f"  OK")
        elif response.status_code == 404:
            print(f"  SQL RPC not available. You need to create tables manually.")
            print(f"\n  Copy this SQL to Supabase Dashboard > SQL Editor:\n")
            print(SQL_SCHEMA)
            return False
        else:
            print(f"  Error {response.status_code}: {response.text}")

    print("\nTables created successfully!")
    return True


if __name__ == "__main__":
    create_tables()
