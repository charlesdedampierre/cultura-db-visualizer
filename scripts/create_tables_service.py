"""Create tables in Supabase using service key and SQL execution."""

import os
import httpx
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_Project_URL")
SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
PROJECT_REF = "ucfmffrrhbwxrfcfkxkg"

SQL_STATEMENTS = [
    """CREATE TABLE IF NOT EXISTS polities (
        id BIGINT PRIMARY KEY,
        name TEXT,
        type TEXT,
        wikipedia_url TEXT,
        wikidata_id TEXT,
        individuals_count INTEGER,
        display_mode TEXT DEFAULT 'both'
    )""",
    """CREATE TABLE IF NOT EXISTS polity_periods (
        id BIGINT PRIMARY KEY,
        polity_id BIGINT REFERENCES polities(id),
        polity_name TEXT,
        from_year INTEGER,
        to_year INTEGER,
        area REAL,
        geometry TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS cities (
        id TEXT PRIMARY KEY,
        name_en TEXT,
        lat REAL,
        lon REAL,
        iso_country_name TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS individuals_light (
        wikidata_id TEXT,
        name_en TEXT,
        occupations_en TEXT,
        sitelinks_count INTEGER,
        impact_date INTEGER,
        impact_date_raw INTEGER,
        polity_id BIGINT,
        birthcity_id TEXT,
        deathcity_id TEXT,
        PRIMARY KEY (wikidata_id, polity_id)
    )""",
    """CREATE TABLE IF NOT EXISTS evolution_cache (
        polity_id BIGINT,
        year INTEGER,
        count INTEGER,
        PRIMARY KEY (polity_id, year)
    )""",
    """CREATE TABLE IF NOT EXISTS top_cities_cache (
        polity_id BIGINT,
        city_id TEXT,
        city_name TEXT,
        lat REAL,
        lon REAL,
        individual_count INTEGER,
        PRIMARY KEY (polity_id, city_id)
    )""",
    "CREATE INDEX IF NOT EXISTS idx_pp_polity ON polity_periods(polity_id)",
    "CREATE INDEX IF NOT EXISTS idx_pp_years ON polity_periods(from_year, to_year)",
    "CREATE INDEX IF NOT EXISTS idx_il_polity ON individuals_light(polity_id)",
    "CREATE INDEX IF NOT EXISTS idx_il_polity_sitelinks ON individuals_light(polity_id, sitelinks_count DESC)",
    "CREATE INDEX IF NOT EXISTS idx_il_polity_impact ON individuals_light(polity_id, impact_date)",
]

def create_tables():
    print(f"Using Supabase URL: {SUPABASE_URL}")
    print(f"Project ref: {PROJECT_REF}")

    # Use the Supabase SQL execution endpoint (Management API style)
    # Try the /sql endpoint with service key
    headers = {
        "apikey": SERVICE_KEY,
        "Authorization": f"Bearer {SERVICE_KEY}",
        "Content-Type": "application/json",
    }

    # First, let's test the connection by listing tables
    print("\nTesting connection...")
    test_response = httpx.get(
        f"{SUPABASE_URL}/rest/v1/",
        headers=headers,
        timeout=30,
    )
    print(f"Connection test: {test_response.status_code}")

    if test_response.status_code == 200:
        print("Connection successful!")
        existing_tables = list(test_response.json().keys()) if test_response.json() else []
        print(f"Existing tables: {existing_tables}")

    # Try using pg_catalog to check if we can run queries
    print("\nAttempting to create tables via REST API...")

    # The service key allows us to use the Data API
    # We need to use a workaround - create tables via migrations or direct SQL

    # Check if we can use the sql endpoint
    sql_endpoint = f"{SUPABASE_URL}/rest/v1/rpc/exec_sql"

    for i, sql in enumerate(SQL_STATEMENTS, 1):
        table_name = sql.split()[5] if "CREATE TABLE" in sql else sql.split()[-1].split("(")[0]
        print(f"\n[{i}/{len(SQL_STATEMENTS)}] {table_name}...")

        response = httpx.post(
            sql_endpoint,
            headers=headers,
            json={"sql": sql},
            timeout=30,
        )

        if response.status_code == 404:
            print("  SQL RPC function not available.")
            print("\n" + "="*50)
            print("The exec_sql function doesn't exist in your Supabase project.")
            print("Please create the tables manually in the SQL Editor.")
            print("="*50)
            print("\nGo to: https://supabase.com/dashboard/project/ucfmffrrhbwxrfcfkxkg/sql/new")
            print("\nAnd paste this SQL:\n")
            print(";\n".join(SQL_STATEMENTS) + ";")
            return False
        elif response.status_code in [200, 201]:
            print(f"  OK")
        else:
            print(f"  Status {response.status_code}: {response.text[:200]}")

    return True

if __name__ == "__main__":
    create_tables()
