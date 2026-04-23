"""
Compute the peak year for each (polity_id, city_id) in top_cities_cache.

"Peak year" = the year Y that maximizes the number of individuals whose
impact_date falls in the 25-year window [Y-12, Y+12] — matching the logic
used by Dynamic mode on the map (see backend/routes/cities.py::get_polity_cities_dynamic
and the client-side window in frontend/src/components/WorldMap.tsx).

Source of individuals: humans_clean.sqlite3, using the same join as
scripts/upload_to_supabase.py (individuals_cliopatria + individuals_keys),
so that the city_id matches what lives in individuals_light / top_cities_cache.

Estimated duration: ~2 min to build in memory, ~15-20 min to upload ~650k rows.

Usage:
    python scripts/compute_city_peak_year.py
"""

import os
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

from dotenv import load_dotenv
from tqdm import tqdm

# Make the backend package importable
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))
load_dotenv(project_root / ".env")

from backend.database import get_db  # noqa: E402

HUMANS_DB_PATH = Path(
    "/Users/charlesdedampierre/Desktop/Rsearch Folder/cultura_database/data/humans_clean.sqlite3"
)


def compute_peak_year(years: list[int]) -> int:
    """Return the year Y that maximizes the count of entries in [Y-12, Y+12].

    Uses a sliding window over sorted years. When the optimal window covers
    entries from years[left]..years[right], we pick the midpoint — this
    guarantees every individual in that cluster lands within 12 years of Y,
    matching the Dynamic-mode window.
    """
    if not years:
        return 0
    years_sorted = sorted(years)
    n = len(years_sorted)

    best_count = 0
    best_left = 0
    best_right = 0
    left = 0
    for right in range(n):
        while years_sorted[right] - years_sorted[left] > 24:
            left += 1
        count = right - left + 1
        if count > best_count:
            best_count = count
            best_left = left
            best_right = right

    return (years_sorted[best_left] + years_sorted[best_right]) // 2


def load_individual_years() -> dict[tuple[int, str], list[int]]:
    """Load (polity_id, city_id) -> [impact_date, ...] from the SQLite source."""
    print(f"Reading individuals from {HUMANS_DB_PATH}...")
    conn = sqlite3.connect(HUMANS_DB_PATH)
    conn.row_factory = sqlite3.Row

    cursor = conn.cursor()
    cursor.execute(
        "SELECT COUNT(*) FROM individuals_cliopatria WHERE impact_date IS NOT NULL"
    )
    total = cursor.fetchone()[0]

    cursor.execute(
        """
        SELECT
            ic.polity_id,
            ic.impact_date,
            ik.birthcity_id,
            ik.deathcity_id
        FROM individuals_cliopatria ic
        LEFT JOIN individuals_keys ik ON ic.wikidata_id = ik.wikidata_id
        WHERE ic.impact_date IS NOT NULL
        """
    )

    groups: dict[tuple[int, str], list[int]] = defaultdict(list)

    for row in tqdm(cursor, total=total, desc="Reading individuals"):
        city_id = row["birthcity_id"] or row["deathcity_id"]
        if not city_id:
            continue
        polity_id_str = row["polity_id"]
        if polity_id_str is None:
            continue
        year = row["impact_date"]
        for pid_str in str(polity_id_str).split(";"):
            pid_str = pid_str.strip()
            if not pid_str.isdigit():
                continue
            pid = int(pid_str)
            groups[(pid, city_id)].append(year)

    conn.close()
    print(f"  Grouped into {len(groups):,} (polity_id, city_id) pairs")
    return groups


def fetch_existing_pairs(db) -> set[tuple[int, str]]:
    """Fetch all existing (polity_id, city_id) pairs from top_cities_cache."""
    print("Fetching existing (polity_id, city_id) pairs from top_cities_cache...")
    pairs: set[tuple[int, str]] = set()
    # Supabase caps responses at 1000 rows — so we paginate in page_size chunks.
    page_size = 1000
    start = 0
    with tqdm(desc="Fetching cache pairs") as pbar:
        while True:
            resp = (
                db.table("top_cities_cache")
                .select("polity_id, city_id")
                .order("polity_id")
                .order("city_id")
                .range(start, start + page_size - 1)
                .execute()
            )
            rows = resp.data or []
            if not rows:
                break
            for r in rows:
                pairs.add((int(r["polity_id"]), r["city_id"]))
            pbar.update(len(rows))
            if len(rows) < page_size:
                break
            start += page_size
    print(f"  Found {len(pairs):,} existing pairs in cache")
    return pairs


def main() -> None:
    groups = load_individual_years()

    print("Computing peak year per pair (25-year sliding window)...")
    peak_years: dict[tuple[int, str], int] = {}
    for key, years in tqdm(groups.items(), desc="Computing peak years"):
        peak_years[key] = compute_peak_year(years)

    db = get_db()
    existing = fetch_existing_pairs(db)

    # Only keep pairs that actually live in top_cities_cache
    to_update = [
        {"polity_id": pid, "city_id": cid, "peak_year": peak_years[(pid, cid)]}
        for (pid, cid) in existing
        if (pid, cid) in peak_years
    ]
    print(f"Will upsert peak_year for {len(to_update):,} rows")

    batch_size = 1000
    for i in tqdm(range(0, len(to_update), batch_size), desc="Uploading"):
        batch = to_update[i : i + batch_size]
        db.table("top_cities_cache").upsert(
            batch, on_conflict="polity_id,city_id"
        ).execute()

    print("Done!")


if __name__ == "__main__":
    main()
