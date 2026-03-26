"""
Create tables in Supabase.

This script outputs the SQL schema needed for the visualizer.
Copy and paste the SQL into Supabase Dashboard > SQL Editor to create tables.

Tables:
- polities: Polity metadata with display_mode
- polity_periods: Geometries with time periods
- cities: City coordinates
- individuals_light: Individual-polity pairs
- evolution_cache: Pre-computed counts per polity/year
- top_cities_cache: Pre-computed top cities per polity

Usage:
    python scripts/create_tables.py
"""

SQL_SCHEMA = """
-- Polities table
CREATE TABLE IF NOT EXISTS polities (
    id BIGINT PRIMARY KEY,
    name TEXT,
    type TEXT,
    wikipedia_url TEXT,
    wikidata_id TEXT,
    individuals_count INTEGER,
    display_mode TEXT DEFAULT 'both'
);

-- Polity periods with geometries
CREATE TABLE IF NOT EXISTS polity_periods (
    id BIGINT PRIMARY KEY,
    polity_id BIGINT REFERENCES polities(id),
    polity_name TEXT,
    from_year INTEGER,
    to_year INTEGER,
    area REAL,
    geometry TEXT
);

-- Cities
CREATE TABLE IF NOT EXISTS cities (
    id TEXT PRIMARY KEY,
    name_en TEXT,
    lat REAL,
    lon REAL,
    iso_country_name TEXT
);

-- Individuals (one row per individual-polity pair)
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

-- Evolution cache (pre-computed counts per polity/year)
CREATE TABLE IF NOT EXISTS evolution_cache (
    polity_id BIGINT REFERENCES polities(id),
    year INTEGER,
    count INTEGER,
    PRIMARY KEY (polity_id, year)
);

-- Top cities cache (pre-computed top cities per polity)
CREATE TABLE IF NOT EXISTS top_cities_cache (
    polity_id BIGINT REFERENCES polities(id),
    city_id TEXT,
    city_name TEXT,
    lat REAL,
    lon REAL,
    individual_count INTEGER,
    PRIMARY KEY (polity_id, city_id)
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_pp_polity ON polity_periods(polity_id);
CREATE INDEX IF NOT EXISTS idx_pp_years ON polity_periods(from_year, to_year);
CREATE INDEX IF NOT EXISTS idx_il_polity ON individuals_light(polity_id);
CREATE INDEX IF NOT EXISTS idx_il_polity_sitelinks ON individuals_light(polity_id, sitelinks_count DESC);
CREATE INDEX IF NOT EXISTS idx_il_polity_impact ON individuals_light(polity_id, impact_date);
CREATE INDEX IF NOT EXISTS idx_tcc_polity ON top_cities_cache(polity_id);

-- Enable text search on individual names
CREATE INDEX IF NOT EXISTS idx_il_name_trgm ON individuals_light USING gin (name_en gin_trgm_ops);
"""

def main():
    print("=" * 60)
    print("Supabase Schema")
    print("=" * 60)
    print()
    print("Copy and paste the following SQL into Supabase Dashboard > SQL Editor:")
    print()
    print("-" * 60)
    print(SQL_SCHEMA)
    print("-" * 60)
    print()
    print("Note: You may need to enable the pg_trgm extension first:")
    print("  CREATE EXTENSION IF NOT EXISTS pg_trgm;")


if __name__ == "__main__":
    main()
