"""Create tables in Supabase using direct Postgres connection."""

import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

DB_PASSWORD = os.getenv("SUPABASE_DB_PASSWORD")
PROJECT_REF = "ucfmffrrhbwxrfcfkxkg"

# Try different EU regions
EU_REGIONS = ["eu-west-1", "eu-west-2", "eu-west-3", "eu-central-1"]


def get_connection():
    """Try connecting to different EU regions."""
    for region in EU_REGIONS:
        conn_str = f"postgresql://postgres.{PROJECT_REF}:{DB_PASSWORD}@aws-0-{region}.pooler.supabase.com:6543/postgres"
        print(f"Trying {region}...")
        try:
            conn = psycopg2.connect(conn_str, connect_timeout=10)
            print(f"Connected via {region}!")
            return conn
        except Exception as e:
            print(f"  Failed: {e}")

    # Try direct connection (not pooler)
    print("Trying direct connection...")
    conn_str = f"postgresql://postgres:{DB_PASSWORD}@db.{PROJECT_REF}.supabase.co:5432/postgres"
    try:
        conn = psycopg2.connect(conn_str, connect_timeout=10)
        print("Connected directly!")
        return conn
    except Exception as e:
        print(f"  Failed: {e}")

    raise Exception("Could not connect to any region")


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
    print("Connecting to Supabase PostgreSQL...")

    conn = get_connection()
    conn.autocommit = True
    cursor = conn.cursor()

    print("Creating tables...")
    cursor.execute(SQL_SCHEMA)

    print("Tables created successfully!")

    # Verify tables exist
    cursor.execute(
        """
        SELECT table_name FROM information_schema.tables
        WHERE table_schema = 'public'
        AND table_type = 'BASE TABLE'
        ORDER BY table_name;
    """
    )

    tables = cursor.fetchall()
    print(f"\nTables in database: {[t[0] for t in tables]}")

    cursor.close()
    conn.close()


if __name__ == "__main__":
    create_tables()
