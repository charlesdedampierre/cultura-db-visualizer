"""
Backfill `cities.is_urban_settlement` from humans_clean.sqlite3 and purge
rows from `top_cities_cache` that belong to non-urban cities.

After this runs, the map + search only surface urban-settlement cities.

Estimated duration: ~3-5 min total.

Usage:
    python scripts/apply_urban_settlement_filter.py
"""

import sqlite3
import sys
from pathlib import Path

from dotenv import load_dotenv
from tqdm import tqdm

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))
load_dotenv(project_root / ".env")

from backend.database import get_db  # noqa: E402

HUMANS_DB_PATH = Path(
    "/Users/charlesdedampierre/Desktop/Rsearch Folder/cultura_database/data/humans_clean.sqlite3"
)


def load_city_flags() -> dict[str, bool]:
    """Return {city_id: is_urban_settlement} from SQLite."""
    print(f"Reading is_urban_settlement from {HUMANS_DB_PATH}...")
    conn = sqlite3.connect(HUMANS_DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT id, COALESCE(is_urban_settlement, 0) FROM cities")
    flags: dict[str, bool] = {}
    for city_id, flag in cur.fetchall():
        flags[city_id] = bool(flag)
    conn.close()
    urban = sum(1 for v in flags.values() if v)
    print(f"  {len(flags):,} cities total — {urban:,} urban, {len(flags) - urban:,} non-urban")
    return flags


def backfill_cities_flag(db, flags: dict[str, bool]) -> None:
    """Upsert is_urban_settlement into cities. PK is id, other cols untouched."""
    print("Backfilling cities.is_urban_settlement...")
    records = [{"id": cid, "is_urban_settlement": urban} for cid, urban in flags.items()]
    batch_size = 1000
    for i in tqdm(range(0, len(records), batch_size), desc="Updating cities"):
        batch = records[i : i + batch_size]
        db.table("cities").upsert(batch, on_conflict="id").execute()


def purge_non_urban_from_cache(db, flags: dict[str, bool]) -> None:
    """Delete rows from top_cities_cache whose city_id is non-urban.

    Non-urban = is_urban_settlement is False OR the city is not in the flags
    map at all (safety: treat unknown as non-urban).
    """
    print("Fetching city_ids present in top_cities_cache...")
    cache_city_ids: set[str] = set()
    page_size = 1000
    start = 0
    with tqdm(desc="Scanning cache") as pbar:
        while True:
            resp = (
                db.table("top_cities_cache")
                .select("city_id")
                .order("polity_id")
                .order("city_id")
                .range(start, start + page_size - 1)
                .execute()
            )
            rows = resp.data or []
            if not rows:
                break
            for r in rows:
                cache_city_ids.add(r["city_id"])
            pbar.update(len(rows))
            if len(rows) < page_size:
                break
            start += page_size

    non_urban_ids = [cid for cid in cache_city_ids if not flags.get(cid, False)]
    print(f"  {len(cache_city_ids):,} unique cities in cache — {len(non_urban_ids):,} non-urban to remove")

    if not non_urban_ids:
        print("Nothing to purge.")
        return

    # Delete in chunks — Supabase .in_() filter gets unwieldy past ~500 values.
    chunk = 400
    for i in tqdm(range(0, len(non_urban_ids), chunk), desc="Deleting"):
        ids = non_urban_ids[i : i + chunk]
        db.table("top_cities_cache").delete().in_("city_id", ids).execute()


def main() -> None:
    flags = load_city_flags()
    db = get_db()
    backfill_cities_flag(db, flags)
    purge_non_urban_from_cache(db, flags)

    r = db.table("top_cities_cache").select("city_id", count="exact").limit(1).execute()
    print(f"\ntop_cities_cache now has {r.count:,} rows")
    print("Done!")


if __name__ == "__main__":
    main()
