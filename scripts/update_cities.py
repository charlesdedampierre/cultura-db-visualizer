"""
Update top_cities_cache in Supabase from humans_clean database.

This is an incremental update script for just the cities data.
Use this when only the cities need to be refreshed.
For a full data refresh, use upload_to_supabase.py instead.

Usage:
    python scripts/update_cities.py
"""

import os
import sqlite3
import pandas as pd
from pathlib import Path
from dotenv import load_dotenv
from supabase import create_client
from tqdm import tqdm

# Load environment variables
load_dotenv(Path(__file__).parent.parent / ".env")

# Configuration
HUMANS_DB_PATH = Path("/Users/charlesdedampierre/Desktop/Rsearch Folder/cultura_database/data/humans_clean.sqlite3")
SUPABASE_URL = os.getenv("SUPABASE_Project_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

# Maximum cities per polity
MAX_CITIES_PER_POLITY = 100


def get_supabase_client():
    """Get Supabase client."""
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise ValueError("Missing SUPABASE_Project_URL or SUPABASE_SERVICE_KEY in .env")
    return create_client(SUPABASE_URL, SUPABASE_KEY)


def extract_cities():
    """Extract cities per polity from humans_clean database."""
    print(f"Connecting to {HUMANS_DB_PATH}...")
    conn = sqlite3.connect(HUMANS_DB_PATH)

    print("Extracting birth cities...")
    birth_df = pd.read_sql_query("""
        SELECT
            ic.polity_id,
            i.birthcity_en as city_name,
            i.wikidata_id
        FROM individuals_cliopatria ic
        JOIN individuals i ON ic.wikidata_id = i.wikidata_id
        WHERE ic.polity_id IS NOT NULL
          AND i.birthcity_en IS NOT NULL
          AND i.birthcity_en != ''
    """, conn)
    print(f"  Found {len(birth_df):,} birth records")

    print("Extracting death cities...")
    death_df = pd.read_sql_query("""
        SELECT
            ic.polity_id,
            i.deathcity_en as city_name,
            i.wikidata_id
        FROM individuals_cliopatria ic
        JOIN individuals i ON ic.wikidata_id = i.wikidata_id
        WHERE ic.polity_id IS NOT NULL
          AND i.deathcity_en IS NOT NULL
          AND i.deathcity_en != ''
    """, conn)
    print(f"  Found {len(death_df):,} death records")

    print("Loading cities with coordinates...")
    cities_df = pd.read_sql_query("""
        SELECT id as city_id, name_en, lat, lon
        FROM cities
        WHERE lat IS NOT NULL AND lon IS NOT NULL
    """, conn)
    print(f"  Found {len(cities_df):,} cities with coordinates")

    conn.close()

    # Explode compound polity IDs
    print("Exploding compound polity IDs...")

    def explode_polity_ids(df):
        rows = []
        for _, row in df.iterrows():
            polity_ids = str(row['polity_id']).split(';')
            for pid in polity_ids:
                pid = pid.strip()
                if pid.isdigit():
                    rows.append({
                        'polity_id': int(pid),
                        'city_name': row['city_name'],
                        'wikidata_id': row['wikidata_id']
                    })
        return pd.DataFrame(rows)

    birth_exploded = explode_polity_ids(birth_df)
    death_exploded = explode_polity_ids(death_df)
    print(f"  Birth records after exploding: {len(birth_exploded):,}")
    print(f"  Death records after exploding: {len(death_exploded):,}")

    # Combine and count
    print("Computing city counts per polity...")
    all_records = pd.concat([birth_exploded, death_exploded])
    city_counts = all_records.groupby(['polity_id', 'city_name']).agg(
        individual_count=('wikidata_id', 'nunique')
    ).reset_index()

    # Join with cities (case-insensitive, deduplicated)
    print("Joining with city coordinates...")
    city_counts['city_name_lower'] = city_counts['city_name'].str.lower()
    cities_df['name_en_lower'] = cities_df['name_en'].str.lower()

    # Deduplicate by lowest Q-number (most notable)
    cities_dedup = cities_df.copy()
    cities_dedup['q_num'] = cities_dedup['city_id'].str.extract(r'Q(\d+)').astype(float)
    cities_dedup = cities_dedup.sort_values('q_num').drop_duplicates(subset=['name_en_lower'], keep='first')

    result = pd.merge(
        city_counts,
        cities_dedup[['city_id', 'name_en_lower', 'lat', 'lon']],
        left_on='city_name_lower',
        right_on='name_en_lower',
        how='inner'
    )

    # Aggregate duplicates: same city might appear with different name variations
    # Sum individual_count for duplicate (polity_id, city_id) pairs
    result_agg = result.groupby(['polity_id', 'city_id']).agg({
        'city_name': 'first',  # Keep first city name
        'lat': 'first',
        'lon': 'first',
        'individual_count': 'sum'  # Sum counts from name variations
    }).reset_index()

    # Keep top N cities per polity
    result_agg = result_agg.sort_values(['polity_id', 'individual_count'], ascending=[True, False])
    result_top = result_agg.groupby('polity_id').head(MAX_CITIES_PER_POLITY)
    result_top = result_top[['polity_id', 'city_id', 'city_name', 'lat', 'lon', 'individual_count']]

    # Clean data
    result_top = result_top.dropna()

    # Final deduplication check (should be clean, but ensure no duplicates)
    result_top = result_top.drop_duplicates(subset=['polity_id', 'city_id'], keep='first')
    result_top['polity_id'] = result_top['polity_id'].astype(int)
    result_top['individual_count'] = result_top['individual_count'].astype(int)

    print(f"\nExtraction complete:")
    print(f"  Total city-polity entries: {len(result_top):,}")
    print(f"  Unique polities: {result_top['polity_id'].nunique():,}")
    print(f"  Unique cities: {result_top['city_id'].nunique():,}")

    return result_top


def upload_to_supabase(df):
    """Upload cities data to Supabase."""
    print("\nConnecting to Supabase...")
    supabase = get_supabase_client()

    # Clear existing data
    print("Clearing existing top_cities_cache...")
    supabase.table("top_cities_cache").delete().neq("polity_id", -999999).execute()

    # Prepare records
    records = df.to_dict('records')

    # Upload in batches using upsert to handle duplicates
    batch_size = 1000
    total_batches = (len(records) + batch_size - 1) // batch_size

    print(f"Uploading {len(records):,} records in {total_batches} batches...")
    for i in tqdm(range(0, len(records), batch_size), desc="Uploading"):
        batch = records[i:i + batch_size]
        supabase.table("top_cities_cache").upsert(batch).execute()

    print("Upload complete!")


def main():
    print("=" * 60)
    print("Update Cities Script")
    print("=" * 60)

    df = extract_cities()
    upload_to_supabase(df)

    print("\nDone!")


if __name__ == "__main__":
    main()
