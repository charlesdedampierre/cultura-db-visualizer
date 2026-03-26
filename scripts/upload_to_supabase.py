"""
Upload data from humans_clean database directly to Supabase.

This is the main data pipeline script. It extracts all data from humans_clean.sqlite3
and uploads it to Supabase tables.

Tables uploaded:
- polities: Polity metadata with display_mode for hierarchy toggle
- polity_periods: Geometries with time periods
- cities: City coordinates
- individuals_light: One row per (individual, polity) pair
- evolution_cache: Pre-computed counts per polity/year
- top_cities_cache: Pre-computed top 100 cities per polity

Usage:
    python scripts/upload_to_supabase.py

Environment variables required in .env:
    SUPABASE_Project_URL
    SUPABASE_SERVICE_KEY
"""

import os
import sqlite3
import json
from pathlib import Path
from collections import defaultdict
from dotenv import load_dotenv
from supabase import create_client
from tqdm import tqdm

# Load environment variables
load_dotenv(Path(__file__).parent.parent / ".env")

# Configuration
HUMANS_DB_PATH = Path(
    "/Users/charlesdedampierre/Desktop/Rsearch Folder/cultura_database/data/humans_clean.sqlite3"
)
CLIO_DB_PATH = Path(
    "/Users/charlesdedampierre/Desktop/Rsearch Folder/cliopatria_data/processing/data/cliopatria.db"
)

SUPABASE_URL = os.getenv("SUPABASE_Project_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")


def get_supabase_client():
    """Get Supabase client."""
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise ValueError("Missing SUPABASE_Project_URL or SUPABASE_SERVICE_KEY in .env")
    return create_client(SUPABASE_URL, SUPABASE_KEY)


def floor_to_25(year: int) -> int:
    """Floor year to nearest 25-year bucket."""
    if year >= 0:
        return (year // 25) * 25
    else:
        return -(((-year - 1) // 25 + 1) * 25) if year % 25 != 0 else year


def simplify_geometry(geom_json: str, tolerance: float = 0.1) -> str:
    """Simplify geometry if shapely is available."""
    try:
        from shapely.geometry import shape
        from shapely import simplify

        geom = shape(json.loads(geom_json))
        simplified = simplify(geom, tolerance=tolerance, preserve_topology=True)
        return json.dumps(simplified.__geo_interface__)
    except ImportError:
        return geom_json
    except Exception:
        return geom_json


def build_display_mode_mapping(source_conn, clio_conn):
    """Determine display_mode for each polity based on hierarchy."""
    source_cur = source_conn.cursor()

    # Get all polities
    source_cur.execute("SELECT id, name, number_individuals FROM polities_cliopatria")
    all_polities = {}
    for row in source_cur:
        all_polities[row["id"]] = {
            "name": row["name"],
            "count": row["number_individuals"],
        }

    # Find parenthesized/non-parenthesized pairs
    source_cur.execute(
        """
        SELECT p1.id as paren_id, p1.number_individuals as paren_count,
               p2.id as non_paren_id, p2.number_individuals as non_paren_count
        FROM polities_cliopatria p1
        JOIN polities_cliopatria p2 ON p2.name = TRIM(p1.name, '()')
        WHERE p1.name LIKE '(%'
    """
    )
    pairs = {row["paren_id"]: dict(row) for row in source_cur}

    # Classify parenthesized polities
    skip_ids = set()
    aggregate_ids = set()

    for pid, info in all_polities.items():
        if not info["name"].startswith("("):
            continue
        if pid in pairs:
            if pairs[pid]["paren_count"] == pairs[pid]["non_paren_count"]:
                skip_ids.add(pid)
            else:
                aggregate_ids.add(pid)
        else:
            aggregate_ids.add(pid)

    # Get hierarchy from cliopatria.db
    children_of_aggregates = set()
    if clio_conn:
        clio_cur = clio_conn.cursor()
        clio_cur.execute(
            """
            SELECT polity_id, level1_id
            FROM polity_hierarchy_levels
            WHERE depth > 0
        """
        )
        for row in clio_cur:
            if row["level1_id"] in aggregate_ids:
                children_of_aggregates.add(row["polity_id"])

    # Build display_mode mapping
    display_mode = {}
    for pid in all_polities:
        if pid in skip_ids:
            display_mode[pid] = "skip"
        elif pid in aggregate_ids:
            display_mode[pid] = "aggregate"
        elif pid in children_of_aggregates and pid not in aggregate_ids:
            display_mode[pid] = "leaf"
        else:
            display_mode[pid] = "both"

    return display_mode, skip_ids


def upload_polities(source_conn, supabase, display_mode):
    """Upload polities table."""
    print("\n1. Uploading polities...")
    cursor = source_conn.cursor()
    cursor.execute("SELECT * FROM polities_cliopatria")
    rows = cursor.fetchall()

    data = []
    for row in tqdm(rows, desc="Preparing polities"):
        pid = row["id"]
        mode = display_mode.get(pid, "both")
        data.append(
            {
                "id": pid,
                "name": row["name"],
                "type": row["type"],
                "wikipedia_url": row["wikipedia_url"],
                "wikidata_id": row["wikidata_id"],
                "individuals_count": row["number_individuals"],
                "display_mode": mode,
            }
        )

    # Clear and upload
    print("  Clearing existing polities...")
    supabase.table("polities").delete().neq("id", -999999).execute()

    batch_size = 1000
    for i in tqdm(range(0, len(data), batch_size), desc="Uploading polities"):
        batch = data[i : i + batch_size]
        supabase.table("polities").insert(batch).execute()

    print(f"  Uploaded {len(data):,} polities")


def upload_polity_periods(source_conn, supabase):
    """Upload polity_periods table."""
    print("\n2. Uploading polity_periods...")
    cursor = source_conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM cliopatria_polity_periods")
    total = cursor.fetchone()[0]

    cursor.execute("SELECT * FROM cliopatria_polity_periods")

    # Clear existing
    print("  Clearing existing polity_periods...")
    supabase.table("polity_periods").delete().neq("id", -999999).execute()

    batch_size = 500
    batch = []
    uploaded = 0

    for row in tqdm(cursor, total=total, desc="Processing polity_periods"):
        geom = simplify_geometry(row["geometry"]) if row["geometry"] else None
        batch.append(
            {
                "id": row["id"],
                "polity_id": row["polity_id"],
                "polity_name": row["polity_name"],
                "from_year": row["from_year"],
                "to_year": row["to_year"],
                "area": row["area"],
                "geometry": geom,
            }
        )

        if len(batch) >= batch_size:
            supabase.table("polity_periods").insert(batch).execute()
            uploaded += len(batch)
            batch = []

    if batch:
        supabase.table("polity_periods").insert(batch).execute()
        uploaded += len(batch)

    print(f"  Uploaded {uploaded:,} polity_periods")


def upload_cities(source_conn, supabase):
    """Upload cities table."""
    print("\n3. Uploading cities...")
    cursor = source_conn.cursor()
    cursor.execute("SELECT id, name_en, lat, lon, iso_country_name FROM cities")
    rows = cursor.fetchall()

    data = []
    for row in tqdm(rows, desc="Preparing cities"):
        data.append(
            {
                "id": row["id"],
                "name_en": row["name_en"],
                "lat": row["lat"],
                "lon": row["lon"],
                "iso_country_name": row["iso_country_name"],
            }
        )

    # Clear and upload
    print("  Clearing existing cities...")
    supabase.table("cities").delete().neq("id", "INVALID").execute()

    batch_size = 1000
    for i in tqdm(range(0, len(data), batch_size), desc="Uploading cities"):
        batch = data[i : i + batch_size]
        supabase.table("cities").insert(batch).execute()

    print(f"  Uploaded {len(data):,} cities")


def upload_individuals(source_conn, supabase, skip_ids):
    """Upload individuals_light table."""
    print("\n4. Uploading individuals_light...")
    cursor = source_conn.cursor()

    query = """
        SELECT
            ic.wikidata_id,
            i.name_en,
            i.occupations_en,
            i.sitelinks_count,
            ic.impact_date,
            ic.polity_id,
            ik.birthcity_id,
            ik.deathcity_id
        FROM individuals_cliopatria ic
        JOIN individuals i ON ic.wikidata_id = i.wikidata_id
        LEFT JOIN individuals_keys ik ON ic.wikidata_id = ik.wikidata_id
        WHERE ic.impact_date IS NOT NULL
    """

    cursor.execute(
        "SELECT COUNT(*) FROM individuals_cliopatria WHERE impact_date IS NOT NULL"
    )
    total = cursor.fetchone()[0]

    cursor.execute(query)

    # Clear existing
    print("  Clearing existing individuals_light...")
    supabase.table("individuals_light").delete().neq("wikidata_id", "INVALID").execute()

    batch_size = 1000
    batch = []
    uploaded = 0
    seen = set()  # Track (wikidata_id, polity_id) pairs

    for row in tqdm(cursor, total=total, desc="Processing individuals"):
        impact_date_rounded = (
            floor_to_25(row["impact_date"]) if row["impact_date"] else None
        )

        polity_id_str = row["polity_id"]
        if polity_id_str is None:
            continue

        polity_ids_raw = str(polity_id_str).split(";")

        for pid_str in polity_ids_raw:
            pid_str = pid_str.strip()
            if not pid_str:
                continue
            try:
                pid = int(pid_str)
            except ValueError:
                continue

            # Skip pure duplicate parenthesized polities
            if pid in skip_ids:
                continue

            # Skip duplicates
            key = (row["wikidata_id"], pid)
            if key in seen:
                continue
            seen.add(key)

            batch.append(
                {
                    "wikidata_id": row["wikidata_id"],
                    "name_en": row["name_en"],
                    "occupations_en": row["occupations_en"],
                    "sitelinks_count": row["sitelinks_count"],
                    "impact_date": impact_date_rounded,
                    "impact_date_raw": row["impact_date"],
                    "polity_id": pid,
                    "birthcity_id": row["birthcity_id"],
                    "deathcity_id": row["deathcity_id"],
                }
            )

            if len(batch) >= batch_size:
                supabase.table("individuals_light").insert(batch).execute()
                uploaded += len(batch)
                batch = []

    if batch:
        supabase.table("individuals_light").insert(batch).execute()
        uploaded += len(batch)

    print(f"  Uploaded {uploaded:,} individual-polity pairs")


def upload_evolution_cache(source_conn, supabase, skip_ids):
    """Compute and upload evolution_cache."""
    print("\n5. Computing and uploading evolution_cache...")
    cursor = source_conn.cursor()

    # Get distinct polity IDs that have individuals
    cursor.execute(
        """
        SELECT DISTINCT ic.polity_id
        FROM individuals_cliopatria ic
        WHERE ic.impact_date IS NOT NULL AND ic.polity_id IS NOT NULL
    """
    )

    polity_ids = set()
    for row in cursor:
        for pid_str in str(row[0]).split(";"):
            pid_str = pid_str.strip()
            if pid_str.isdigit():
                pid = int(pid_str)
                if pid not in skip_ids:
                    polity_ids.add(pid)

    polity_ids = sorted(polity_ids)

    # Clear existing
    print("  Clearing existing evolution_cache...")
    supabase.table("evolution_cache").delete().neq("polity_id", -999999).execute()

    # Compute counts per polity/year
    all_entries = []

    for polity_id in tqdm(polity_ids, desc="Computing evolution"):
        cursor.execute(
            """
            SELECT ic.impact_date, COUNT(DISTINCT ic.wikidata_id) as cnt
            FROM individuals_cliopatria ic
            WHERE ic.polity_id LIKE ? AND ic.impact_date IS NOT NULL
            GROUP BY ic.impact_date
        """,
            (f"%{polity_id}%",),
        )

        year_counts = defaultdict(int)
        for row in cursor:
            year_bucket = floor_to_25(row[0])
            # Verify the polity_id actually contains this polity
            year_counts[year_bucket] += row[1]

        for year, count in year_counts.items():
            all_entries.append(
                {
                    "polity_id": polity_id,
                    "year": year,
                    "count": count,
                }
            )

    # Upload in batches
    batch_size = 1000
    for i in tqdm(
        range(0, len(all_entries), batch_size), desc="Uploading evolution_cache"
    ):
        batch = all_entries[i : i + batch_size]
        supabase.table("evolution_cache").insert(batch).execute()

    print(f"  Uploaded {len(all_entries):,} evolution_cache entries")


def upload_top_cities_cache(source_conn, supabase):
    """Compute and upload top_cities_cache."""
    print("\n6. Computing and uploading top_cities_cache...")

    import pandas as pd

    # Query birth/death cities
    print("  Extracting birth cities...")
    birth_df = pd.read_sql_query(
        """
        SELECT
            ic.polity_id,
            i.birthcity_en as city_name,
            i.wikidata_id
        FROM individuals_cliopatria ic
        JOIN individuals i ON ic.wikidata_id = i.wikidata_id
        WHERE ic.polity_id IS NOT NULL
          AND i.birthcity_en IS NOT NULL
          AND i.birthcity_en != ''
    """,
        source_conn,
    )

    print("  Extracting death cities...")
    death_df = pd.read_sql_query(
        """
        SELECT
            ic.polity_id,
            i.deathcity_en as city_name,
            i.wikidata_id
        FROM individuals_cliopatria ic
        JOIN individuals i ON ic.wikidata_id = i.wikidata_id
        WHERE ic.polity_id IS NOT NULL
          AND i.deathcity_en IS NOT NULL
          AND i.deathcity_en != ''
    """,
        source_conn,
    )

    print("  Loading city coordinates...")
    cities_df = pd.read_sql_query(
        """
        SELECT id as city_id, name_en, lat, lon
        FROM cities
        WHERE lat IS NOT NULL AND lon IS NOT NULL
    """,
        source_conn,
    )

    # Explode compound polity IDs
    print("  Exploding compound polity IDs...")

    def explode_polity_ids(df):
        rows = []
        for _, row in df.iterrows():
            polity_ids = str(row["polity_id"]).split(";")
            for pid in polity_ids:
                pid = pid.strip()
                if pid.isdigit():
                    rows.append(
                        {
                            "polity_id": int(pid),
                            "city_name": row["city_name"],
                            "wikidata_id": row["wikidata_id"],
                        }
                    )
        return pd.DataFrame(rows)

    birth_exploded = explode_polity_ids(birth_df)
    death_exploded = explode_polity_ids(death_df)

    # Combine and count
    print("  Computing city counts per polity...")
    all_records = pd.concat([birth_exploded, death_exploded])
    city_counts = (
        all_records.groupby(["polity_id", "city_name"])
        .agg(individual_count=("wikidata_id", "nunique"))
        .reset_index()
    )

    # Join with cities (case-insensitive, deduplicated)
    city_counts["city_name_lower"] = city_counts["city_name"].str.lower()
    cities_df["name_en_lower"] = cities_df["name_en"].str.lower()

    # Deduplicate by lowest Q-number
    cities_dedup = cities_df.copy()
    cities_dedup["q_num"] = cities_dedup["city_id"].str.extract(r"Q(\d+)").astype(float)
    cities_dedup = cities_dedup.sort_values("q_num").drop_duplicates(
        subset=["name_en_lower"], keep="first"
    )

    result = pd.merge(
        city_counts,
        cities_dedup[["city_id", "name_en_lower", "lat", "lon"]],
        left_on="city_name_lower",
        right_on="name_en_lower",
        how="inner",
    )

    # Keep top 100 cities per polity
    result = result.sort_values(
        ["polity_id", "individual_count"], ascending=[True, False]
    )
    result_top = result.groupby("polity_id").head(100)
    result_top = result_top[
        ["polity_id", "city_id", "city_name", "lat", "lon", "individual_count"]
    ]

    # Clean data
    result_top = result_top.dropna()
    result_top["polity_id"] = result_top["polity_id"].astype(int)
    result_top["individual_count"] = result_top["individual_count"].astype(int)

    print(f"  Total city-polity entries: {len(result_top):,}")

    # Clear and upload
    print("  Clearing existing top_cities_cache...")
    supabase = get_supabase_client()
    supabase.table("top_cities_cache").delete().neq("polity_id", -999999).execute()

    records = result_top.to_dict("records")
    batch_size = 1000
    for i in tqdm(
        range(0, len(records), batch_size), desc="Uploading top_cities_cache"
    ):
        batch = records[i : i + batch_size]
        supabase.table("top_cities_cache").insert(batch).execute()

    print(f"  Uploaded {len(records):,} top_cities_cache entries")


def generate_evolution_json(source_conn, skip_ids, output_path):
    """Generate evolution.json for frontend."""
    print("\n7. Generating evolution.json...")
    cursor = source_conn.cursor()

    # Get distinct polity IDs
    cursor.execute(
        """
        SELECT DISTINCT ic.polity_id
        FROM individuals_cliopatria ic
        WHERE ic.impact_date IS NOT NULL AND ic.polity_id IS NOT NULL
    """
    )

    polity_ids = set()
    for row in cursor:
        for pid_str in str(row[0]).split(";"):
            pid_str = pid_str.strip()
            if pid_str.isdigit():
                pid = int(pid_str)
                if pid not in skip_ids:
                    polity_ids.add(pid)

    polity_ids = sorted(polity_ids)

    evolution_data = {}

    for polity_id in tqdm(polity_ids, desc="Computing evolution"):
        cursor.execute(
            """
            SELECT ic.impact_date, COUNT(DISTINCT ic.wikidata_id) as cnt
            FROM individuals_cliopatria ic
            WHERE ic.polity_id LIKE ? AND ic.impact_date IS NOT NULL
            GROUP BY ic.impact_date
            ORDER BY ic.impact_date
        """,
            (f"%{polity_id}%",),
        )

        year_counts = defaultdict(int)
        for row in cursor:
            year_bucket = floor_to_25(row[0])
            year_counts[year_bucket] += row[1]

        if year_counts:
            evolution_data[str(polity_id)] = [
                {"year": year, "count": count}
                for year, count in sorted(year_counts.items())
            ]

    with open(output_path, "w") as f:
        json.dump(evolution_data, f, separators=(",", ":"))

    print(f"  Generated {output_path} ({len(evolution_data)} polities)")


def generate_occupations_json(source_conn, skip_ids, output_path):
    """Generate occupations.json for frontend."""
    print("\n8. Generating occupations.json...")
    cursor = source_conn.cursor()

    # Get distinct polity IDs
    cursor.execute(
        """
        SELECT DISTINCT ic.polity_id
        FROM individuals_cliopatria ic
        WHERE ic.polity_id IS NOT NULL
    """
    )

    polity_ids = set()
    for row in cursor:
        for pid_str in str(row[0]).split(";"):
            pid_str = pid_str.strip()
            if pid_str.isdigit():
                pid = int(pid_str)
                if pid not in skip_ids:
                    polity_ids.add(pid)

    polity_ids = sorted(polity_ids)

    occupations_data = {}

    for polity_id in tqdm(polity_ids, desc="Computing occupations"):
        cursor.execute(
            """
            SELECT i.occupations_en
            FROM individuals_cliopatria ic
            JOIN individuals i ON ic.wikidata_id = i.wikidata_id
            WHERE ic.polity_id LIKE ? AND i.occupations_en IS NOT NULL
        """,
            (f"%{polity_id}%",),
        )

        occ_counts = defaultdict(int)
        for row in cursor:
            # Split semicolon-separated occupations
            for occ in row[0].split("; "):
                occ = occ.strip()
                if occ:
                    occ_counts[occ] += 1

        if occ_counts:
            # Sort by count descending, take top 20
            sorted_occs = sorted(occ_counts.items(), key=lambda x: x[1], reverse=True)[
                :20
            ]
            occupations_data[str(polity_id)] = [
                {"name": name, "count": count} for name, count in sorted_occs
            ]

    with open(output_path, "w") as f:
        json.dump(occupations_data, f, separators=(",", ":"))

    print(f"  Generated {output_path} ({len(occupations_data)} polities)")


def main():
    print("=" * 60)
    print("Upload humans_clean to Supabase")
    print("=" * 60)
    print(f"Source: {HUMANS_DB_PATH}")
    print(f"Supabase: {SUPABASE_URL}")
    print()

    # Connect to databases
    source_conn = sqlite3.connect(HUMANS_DB_PATH)
    source_conn.text_factory = lambda b: b.decode("utf-8", errors="replace")
    source_conn.row_factory = sqlite3.Row

    clio_conn = None
    if CLIO_DB_PATH.exists():
        clio_conn = sqlite3.connect(CLIO_DB_PATH)
        clio_conn.row_factory = sqlite3.Row
    else:
        print(f"WARNING: Cliopatria DB not found at {CLIO_DB_PATH}")

    supabase = get_supabase_client()

    # Build hierarchy mapping
    print("\n0. Building hierarchy mapping...")
    display_mode, skip_ids = build_display_mode_mapping(source_conn, clio_conn)
    print(f"  Skip IDs: {len(skip_ids)}")

    # Upload all tables
    upload_polities(source_conn, supabase, display_mode)
    upload_polity_periods(source_conn, supabase)
    upload_cities(source_conn, supabase)
    upload_individuals(source_conn, supabase, skip_ids)
    upload_evolution_cache(source_conn, supabase, skip_ids)
    upload_top_cities_cache(source_conn, supabase)

    # Generate JSON files for frontend
    frontend_public = Path(__file__).parent.parent / "frontend" / "public"
    generate_evolution_json(source_conn, skip_ids, frontend_public / "evolution.json")
    generate_occupations_json(
        source_conn, skip_ids, frontend_public / "occupations.json"
    )

    # Close connections
    source_conn.close()
    if clio_conn:
        clio_conn.close()

    print("\n" + "=" * 60)
    print("Upload complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
