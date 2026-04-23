"""
Upload the three precomputed city tables from
data/cities_precomputed/cities_data.sqlite3 into Supabase:

    city_individuals_cache   (~4.5M rows)
    city_evolution_cache     (~0.66M rows)
    city_summary_cache       (~0.25M rows)

All three tables are wiped and re-inserted. Estimated duration: ~20-25 min
(dominated by city_individuals ~4500 batches × ~250ms).

Usage:
    python scripts/upload_city_pages.py
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

LOCAL_DB = project_root / "data" / "cities_precomputed" / "cities_data.sqlite3"
BATCH = 1000


def clear(db, table: str) -> None:
    """Delete all rows from `table`. Supabase imposes a per-statement
    timeout on REST writes, so a single DELETE against a million-row
    table fails. We sweep in chunks ordered by city_id, deleting any
    row whose city_id is at or before a moving cursor."""
    print(f"Clearing {table}...", flush=True)
    chunk = 5000
    while True:
        # Fetch the next batch of primary keys and delete them explicitly —
        # bounded-size delete stays under the timeout.
        ids = (
            db.table(table).select("city_id").order("city_id")
            .range(0, chunk - 1).execute().data
        )
        if not ids:
            break
        unique = list({r["city_id"] for r in ids})
        db.table(table).delete().in_("city_id", unique).execute()


def upload_table(
    db,
    local: sqlite3.Connection,
    src_table: str,
    dest_table: str,
    columns: list[str],
) -> None:
    (total,) = local.execute(f"SELECT COUNT(*) FROM {src_table}").fetchone()
    print(f"\n{src_table} -> {dest_table}: {total:,} rows")

    clear(db, dest_table)

    cur = local.execute(f"SELECT {', '.join(columns)} FROM {src_table}")
    batch: list[dict] = []
    n_uploaded = 0
    with tqdm(total=total, desc=dest_table) as pbar:
        for row in cur:
            batch.append(dict(zip(columns, row)))
            if len(batch) >= BATCH:
                db.table(dest_table).insert(batch).execute()
                n_uploaded += len(batch)
                pbar.update(len(batch))
                batch = []
        if batch:
            db.table(dest_table).insert(batch).execute()
            n_uploaded += len(batch)
            pbar.update(len(batch))
    print(f"  Uploaded {n_uploaded:,} rows")


def main() -> None:
    if not LOCAL_DB.exists():
        raise FileNotFoundError(
            f"{LOCAL_DB} not found — run scripts/precompute_city_pages.py first"
        )
    local = sqlite3.connect(LOCAL_DB)
    # Some rows in the upstream humans_clean data contain bytes that aren't
    # valid UTF-8 (stray surrogate-pair leftovers in occupations_en). The
    # default text_factory raises, so we swap to a lenient decoder that
    # replaces bad bytes with U+FFFD rather than crashing the whole upload.
    local.text_factory = lambda b: b.decode("utf-8", errors="replace")
    db = get_db()

    # Accept a space-separated list of table shortnames to upload. If no args,
    # do all three. Re-runs are safe — each table is cleared first.
    which = set(sys.argv[1:]) or {"summary", "evolution", "individuals"}

    if "summary" in which:
        upload_table(
            db, local, "city_summary", "city_summary_cache",
            ["city_id", "name_en", "lat", "lon",
             "n_individuals", "n_birth", "n_death", "n_both"],
        )
    if "evolution" in which:
        upload_table(
            db, local, "city_evolution", "city_evolution_cache",
            ["city_id", "year", "count"],
        )
    if "individuals" in which:
        upload_table(
            db, local, "city_individuals", "city_individuals_cache",
            ["city_id", "wikidata_id", "name_en", "occupations_en",
             "sitelinks_count", "impact_date_raw", "impact_date",
             "is_birth", "is_death"],
        )

    local.close()
    print("\nDone!")


if __name__ == "__main__":
    main()
