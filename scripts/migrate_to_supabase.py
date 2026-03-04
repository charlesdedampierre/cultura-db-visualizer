"""Migrate SQLite database to Supabase.

This script:
1. Creates tables in Supabase
2. Exports data from SQLite and uploads to Supabase

Usage:
    python scripts/migrate_to_supabase.py
"""

import os
import sqlite3
import json
from pathlib import Path
from dotenv import load_dotenv
from supabase import create_client
from tqdm import tqdm

# Load environment variables
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_Project_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")  # Use service key for full access

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("Missing SUPABASE_Project_URL or SUPABASE_API_KEY in .env")

# Initialize Supabase client
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# SQLite database path
DB_PATH = Path(__file__).parent.parent / "data" / "visualizer.sqlite3"


def get_sqlite_connection():
    """Get SQLite connection."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def migrate_polities():
    """Migrate polities table."""
    print("\n--- Migrating polities ---")
    conn = get_sqlite_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM polities")
    rows = cursor.fetchall()

    data = []
    for row in tqdm(rows, desc="Preparing polities"):
        data.append({
            "id": row["id"],
            "name": row["name"],
            "type": row["type"],
            "wikipedia_url": row["wikipedia_url"],
            "wikidata_id": row["wikidata_id"],
            "individuals_count": row["individuals_count"],
            "display_mode": row["display_mode"],
        })

    # Insert in batches of 1000
    batch_size = 1000
    for i in tqdm(range(0, len(data), batch_size), desc="Uploading polities"):
        batch = data[i:i + batch_size]
        supabase.table("polities").upsert(batch).execute()

    print(f"Migrated {len(data)} polities")
    conn.close()


def migrate_polity_periods():
    """Migrate polity_periods table."""
    print("\n--- Migrating polity_periods ---")
    conn = get_sqlite_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM polity_periods")
    total = cursor.fetchone()[0]

    cursor.execute("SELECT * FROM polity_periods")

    batch_size = 500
    batch = []

    with tqdm(total=total, desc="Migrating polity_periods") as pbar:
        for row in cursor:
            batch.append({
                "id": row["id"],
                "polity_id": row["polity_id"],
                "polity_name": row["polity_name"],
                "from_year": row["from_year"],
                "to_year": row["to_year"],
                "area": row["area"],
                "geometry": row["geometry"],  # Keep as text (JSON string)
            })

            if len(batch) >= batch_size:
                supabase.table("polity_periods").upsert(batch).execute()
                pbar.update(len(batch))
                batch = []

        if batch:
            supabase.table("polity_periods").upsert(batch).execute()
            pbar.update(len(batch))

    print(f"Migrated {total} polity_periods")
    conn.close()


def migrate_cities():
    """Migrate cities table."""
    print("\n--- Migrating cities ---")
    conn = get_sqlite_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM cities")
    rows = cursor.fetchall()

    data = []
    for row in tqdm(rows, desc="Preparing cities"):
        data.append({
            "id": row["id"],
            "name_en": row["name_en"],
            "lat": row["lat"],
            "lon": row["lon"],
            "iso_country_name": row["iso_country_name"],
        })

    batch_size = 1000
    for i in tqdm(range(0, len(data), batch_size), desc="Uploading cities"):
        batch = data[i:i + batch_size]
        supabase.table("cities").upsert(batch).execute()

    print(f"Migrated {len(data)} cities")
    conn.close()


def migrate_individuals_light():
    """Migrate individuals_light table (large table, batch processing)."""
    print("\n--- Migrating individuals_light ---")
    conn = get_sqlite_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM individuals_light")
    total = cursor.fetchone()[0]
    print(f"Total individuals: {total}")

    cursor.execute("SELECT * FROM individuals_light")

    batch_size = 1000
    batch = []

    with tqdm(total=total, desc="Migrating individuals") as pbar:
        for row in cursor:
            batch.append({
                "wikidata_id": row["wikidata_id"],
                "name_en": row["name_en"],
                "occupations_en": row["occupations_en"],
                "sitelinks_count": row["sitelinks_count"],
                "impact_date": row["impact_date"],
                "impact_date_raw": row["impact_date_raw"],
                "polity_id": row["polity_id"],
                "birthcity_id": row["birthcity_id"],
                "deathcity_id": row["deathcity_id"],
            })

            if len(batch) >= batch_size:
                supabase.table("individuals_light").upsert(batch).execute()
                pbar.update(len(batch))
                batch = []

        if batch:
            supabase.table("individuals_light").upsert(batch).execute()
            pbar.update(len(batch))

    print(f"Migrated {total} individuals")
    conn.close()


def migrate_evolution_cache():
    """Migrate evolution_cache table."""
    print("\n--- Migrating evolution_cache ---")
    conn = get_sqlite_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM evolution_cache")
    rows = cursor.fetchall()

    data = []
    for row in tqdm(rows, desc="Preparing evolution_cache"):
        data.append({
            "polity_id": row["polity_id"],
            "year": row["year"],
            "count": row["count"],
        })

    batch_size = 1000
    for i in tqdm(range(0, len(data), batch_size), desc="Uploading evolution_cache"):
        batch = data[i:i + batch_size]
        supabase.table("evolution_cache").upsert(batch).execute()

    print(f"Migrated {len(data)} evolution_cache entries")
    conn.close()


def migrate_top_cities_cache():
    """Migrate top_cities_cache table."""
    print("\n--- Migrating top_cities_cache ---")
    conn = get_sqlite_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM top_cities_cache")
    rows = cursor.fetchall()

    data = []
    for row in tqdm(rows, desc="Preparing top_cities_cache"):
        data.append({
            "polity_id": row["polity_id"],
            "city_id": row["city_id"],
            "city_name": row["city_name"],
            "lat": row["lat"],
            "lon": row["lon"],
            "individual_count": row["individual_count"],
        })

    batch_size = 1000
    for i in tqdm(range(0, len(data), batch_size), desc="Uploading top_cities_cache"):
        batch = data[i:i + batch_size]
        supabase.table("top_cities_cache").upsert(batch).execute()

    print(f"Migrated {len(data)} top_cities_cache entries")
    conn.close()


def main():
    """Run migration."""
    print("=" * 50)
    print("Supabase Migration")
    print("=" * 50)
    print(f"Supabase URL: {SUPABASE_URL}")
    print(f"SQLite DB: {DB_PATH}")
    print()

    # Run migrations
    migrate_polities()
    migrate_polity_periods()
    migrate_cities()
    migrate_evolution_cache()
    migrate_top_cities_cache()
    migrate_individuals_light()  # Last because it's the largest

    print("\n" + "=" * 50)
    print("Migration complete!")
    print("=" * 50)


if __name__ == "__main__":
    main()
