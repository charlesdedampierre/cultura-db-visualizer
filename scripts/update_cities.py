"""
Rebuild top_cities_cache in Supabase from humans_clean.sqlite3.

Key difference vs. the old name-based version:

- Each individual is attributed to their BIRTH CITY Q-ID (fallback: death
  city Q-id) from `individuals_keys`. So Paris, France (Q90) and Paris, TX
  (e.g. Q830149) become DISTINCT rows in the cache — no more silent collapse.
- Only urban settlements (cities.is_urban_settlement = 1) are kept.
- Parent "meta" polities (names starting with '(') are dropped so only leaf
  polities end up on the map.
- `individual_count`, `first_individual_year`, and `peak_year` are all
  computed in the same pass.

Peak year: the year Y that maximises individuals in a 25-year window
[Y-12, Y+12], matching Dynamic-mode behaviour on the map.

Estimated duration: ~5 min (2 min read + 3 min upload).

Usage:
    python scripts/update_cities.py
"""

import os
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

from dotenv import load_dotenv
from tqdm import tqdm

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))
load_dotenv(project_root / ".env")

from supabase import create_client  # noqa: E402

HUMANS_DB_PATH = Path(
    "/Users/charlesdedampierre/Desktop/Rsearch Folder/cultura_database/data/humans_clean.sqlite3"
)
SUPABASE_URL = os.getenv("SUPABASE_Project_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")


def get_supabase_client():
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise ValueError("Missing SUPABASE_Project_URL or SUPABASE_SERVICE_KEY in .env")
    return create_client(SUPABASE_URL, SUPABASE_KEY)


def compute_peak_year(years: list[int]) -> int:
    """Year Y that maximises count in [Y-12, Y+12]. Midpoint of the
    tightest best window."""
    if not years:
        return 0
    ys = sorted(years)
    n = len(ys)
    best_count = 0
    best_left = 0
    best_right = 0
    left = 0
    for right in range(n):
        while ys[right] - ys[left] > 24:
            left += 1
        count = right - left + 1
        if count > best_count:
            best_count = count
            best_left = left
            best_right = right
    return (ys[best_left] + ys[best_right]) // 2


def load_urban_cities() -> dict[str, dict]:
    """Return {city_id: {name_en, lat, lon}} for urban cities with coords."""
    print(f"Reading urban cities from {HUMANS_DB_PATH}...")
    conn = sqlite3.connect(HUMANS_DB_PATH)
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, name_en, lat, lon
        FROM cities
        WHERE is_urban_settlement = 1
          AND lat IS NOT NULL
          AND lon IS NOT NULL
        """
    )
    cities = {
        cid: {"name_en": name, "lat": lat, "lon": lon}
        for cid, name, lat, lon in cur.fetchall()
    }
    conn.close()
    print(f"  {len(cities):,} urban cities with coordinates")
    return cities


def aggregate_individuals(urban_cities: dict[str, dict]) -> list[dict]:
    """Group individuals by (polity_id, city_id). Return cache rows.

    - city_id = birthcity_id, fallback deathcity_id.
    - Only counts cities that are in the urban set.
    - Individual count is unique wikidata_ids (not rows).
    """
    print("Reading individuals with polity + city Q-ids...")
    conn = sqlite3.connect(HUMANS_DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(
        "SELECT COUNT(*) FROM individuals_cliopatria WHERE impact_date IS NOT NULL"
    )
    total = cur.fetchone()[0]
    cur.execute(
        """
        SELECT
            ic.polity_id,
            ic.wikidata_id,
            ic.impact_date,
            ik.birthcity_id,
            ik.deathcity_id
        FROM individuals_cliopatria ic
        LEFT JOIN individuals_keys ik ON ic.wikidata_id = ik.wikidata_id
        WHERE ic.impact_date IS NOT NULL
        """
    )

    # group[(polity_id, city_id)] = {"wikidata_ids": set(), "years": [int]}
    groups: dict[tuple[int, str], dict] = defaultdict(
        lambda: {"wikidata_ids": set(), "years": []}
    )

    for row in tqdm(cur, total=total, desc="Reading individuals"):
        city_id = row["birthcity_id"] or row["deathcity_id"]
        if not city_id or city_id not in urban_cities:
            continue
        polity_id_raw = row["polity_id"]
        if polity_id_raw is None:
            continue
        wid = row["wikidata_id"]
        year = row["impact_date"]
        for pid_str in str(polity_id_raw).split(";"):
            pid_str = pid_str.strip()
            if not pid_str.isdigit():
                continue
            pid = int(pid_str)
            key = (pid, city_id)
            g = groups[key]
            g["wikidata_ids"].add(wid)
            g["years"].append(year)

    conn.close()
    print(f"  Aggregated {len(groups):,} (polity_id, city_id) pairs")

    print("Computing individual_count / first_individual_year / peak_year...")
    records: list[dict] = []
    for (pid, cid), g in tqdm(groups.items(), desc="Finalising"):
        years = g["years"]
        city = urban_cities[cid]
        records.append(
            {
                "polity_id": pid,
                "city_id": cid,
                "city_name": city["name_en"],
                "lat": city["lat"],
                "lon": city["lon"],
                "individual_count": len(g["wikidata_ids"]),
                "first_individual_year": min(years) if years else None,
                "peak_year": compute_peak_year(years) if years else None,
            }
        )
    return records


def rebuild_cache(db, records: list[dict]) -> None:
    print("Clearing existing top_cities_cache...")
    db.table("top_cities_cache").delete().neq("polity_id", -999999).execute()

    print(f"Uploading {len(records):,} rows...")
    batch_size = 1000
    for i in tqdm(range(0, len(records), batch_size), desc="Uploading"):
        batch = records[i : i + batch_size]
        db.table("top_cities_cache").insert(batch).execute()


def main() -> None:
    urban_cities = load_urban_cities()
    records = aggregate_individuals(urban_cities)
    db = get_supabase_client()
    rebuild_cache(db, records)
    r = db.table("top_cities_cache").select("city_id", count="exact").limit(1).execute()
    print(f"\ntop_cities_cache now has {r.count:,} rows")
    print("Done!")


if __name__ == "__main__":
    main()
