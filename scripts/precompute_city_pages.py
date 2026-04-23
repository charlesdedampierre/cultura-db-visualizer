"""
Precompute per-city data (individuals list + evolution chart) LOCALLY.

Output: data/cities_precomputed/cities_data.sqlite3 with three tables:

    city_individuals
        (city_id, wikidata_id, name_en, occupations_en, sitelinks_count,
         impact_date_raw, impact_date, is_birth, is_death)
        — one row per (city, individual). is_birth/is_death are 0/1 flags;
          an individual born AND died in the same city gets one row with
          both flags = 1.

    city_evolution
        (city_id, year, count) — count of distinct individuals per 25-year
        bucket, matching the existing polity-evolution format on the map.

    city_summary
        (city_id, name_en, lat, lon, n_individuals, n_birth, n_death, n_both)
        — stats per city, for quick filtering.

Only urban cities (is_urban_settlement = 1) with coordinates are included.
Nothing is written to Supabase — this is a local inspection pass.

Estimated duration: ~2-4 min (single pass of SQL + small Python post-processing).

Usage:
    python scripts/precompute_city_pages.py
"""

import sqlite3
import sys
import time
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

HUMANS_DB_PATH = Path(
    "/Users/charlesdedampierre/Desktop/Rsearch Folder/cultura_database/data/humans_clean.sqlite3"
)
OUTPUT_PATH = project_root / "data" / "cities_precomputed" / "cities_data.sqlite3"


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def main() -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    if OUTPUT_PATH.exists():
        OUTPUT_PATH.unlink()
        log(f"Removed existing {OUTPUT_PATH.name}")

    dest = sqlite3.connect(OUTPUT_PATH)
    dest.execute(f"ATTACH DATABASE '{HUMANS_DB_PATH}' AS src")

    # -- city_individuals --
    # floor_to_25 is expressed inline; SQLite integer division truncates
    # toward zero, so for BCE years we shift first to get a true floor.
    log("Building city_individuals... (long-running join on ~13M × 5.7M)")
    t0 = time.time()
    dest.executescript("""
    CREATE TABLE city_individuals AS
    WITH urban_cities AS (
        SELECT id FROM src.cities
        WHERE is_urban_settlement = 1
          AND lat IS NOT NULL AND lon IS NOT NULL
    ),
    individual_cities AS (
        SELECT wikidata_id, birthcity_id AS city_id, 1 AS is_birth, 0 AS is_death
        FROM src.individuals_keys
        WHERE birthcity_id IS NOT NULL
        UNION ALL
        SELECT wikidata_id, deathcity_id AS city_id, 0 AS is_birth, 1 AS is_death
        FROM src.individuals_keys
        WHERE deathcity_id IS NOT NULL
    ),
    aggregated AS (
        SELECT
            ic.city_id,
            ic.wikidata_id,
            MAX(ic.is_birth) AS is_birth,
            MAX(ic.is_death) AS is_death
        FROM individual_cities ic
        JOIN urban_cities uc ON uc.id = ic.city_id
        GROUP BY ic.city_id, ic.wikidata_id
    ),
    impact_dates AS (
        SELECT wikidata_id, MIN(impact_date) AS impact_date_raw
        FROM src.individuals_cliopatria
        WHERE impact_date IS NOT NULL
        GROUP BY wikidata_id
    )
    SELECT
        a.city_id,
        a.wikidata_id,
        i.name_en,
        i.occupations_en,
        i.sitelinks_count,
        id.impact_date_raw,
        CASE
            WHEN id.impact_date_raw IS NULL THEN NULL
            WHEN id.impact_date_raw >= 0 THEN (id.impact_date_raw / 25) * 25
            ELSE ((id.impact_date_raw - 24) / 25) * 25
        END AS impact_date,
        a.is_birth,
        a.is_death
    FROM aggregated a
    JOIN src.individuals i ON i.wikidata_id = a.wikidata_id
    LEFT JOIN impact_dates id ON id.wikidata_id = a.wikidata_id;

    CREATE INDEX idx_cind_city ON city_individuals(city_id);
    CREATE INDEX idx_cind_wid  ON city_individuals(wikidata_id);
    """)
    (n_individuals,) = dest.execute("SELECT COUNT(*) FROM city_individuals").fetchone()
    log(f"city_individuals: {n_individuals:,} rows (built in {time.time()-t0:.0f}s)")

    # -- city_evolution --
    log("Building city_evolution...")
    t0 = time.time()
    dest.executescript("""
    CREATE TABLE city_evolution AS
    SELECT
        city_id,
        impact_date AS year,
        COUNT(DISTINCT wikidata_id) AS count
    FROM city_individuals
    WHERE impact_date IS NOT NULL
    GROUP BY city_id, impact_date;

    CREATE INDEX idx_cevo_city ON city_evolution(city_id);
    """)
    (n_evo,) = dest.execute("SELECT COUNT(*) FROM city_evolution").fetchone()
    log(f"city_evolution: {n_evo:,} rows (built in {time.time()-t0:.0f}s)")

    # -- city_summary --
    log("Building city_summary...")
    t0 = time.time()
    dest.executescript("""
    CREATE TABLE city_summary AS
    WITH urban_cities AS (
        SELECT id AS city_id, name_en, lat, lon
        FROM src.cities
        WHERE is_urban_settlement = 1
          AND lat IS NOT NULL AND lon IS NOT NULL
    ),
    stats AS (
        SELECT
            city_id,
            COUNT(DISTINCT wikidata_id) AS n_individuals,
            SUM(is_birth) AS n_birth,
            SUM(is_death) AS n_death,
            SUM(CASE WHEN is_birth = 1 AND is_death = 1 THEN 1 ELSE 0 END) AS n_both
        FROM city_individuals
        GROUP BY city_id
    )
    SELECT
        s.city_id,
        uc.name_en,
        uc.lat,
        uc.lon,
        s.n_individuals,
        s.n_birth,
        s.n_death,
        s.n_both
    FROM stats s
    JOIN urban_cities uc ON uc.city_id = s.city_id;

    CREATE INDEX idx_csum_city ON city_summary(city_id);
    CREATE INDEX idx_csum_n    ON city_summary(n_individuals DESC);
    """)
    (n_sum,) = dest.execute("SELECT COUNT(*) FROM city_summary").fetchone()
    log(f"city_summary: {n_sum:,} rows (built in {time.time()-t0:.0f}s)")

    dest.commit()

    # -- quick bucketed overview for sanity --
    print()
    print("City counts by individuals bucket:")
    for threshold in (1, 10, 100, 1000, 10000):
        (n,) = dest.execute(
            "SELECT COUNT(*) FROM city_summary WHERE n_individuals >= ?", (threshold,)
        ).fetchone()
        print(f"  ≥ {threshold:>6,} individuals: {n:>7,} cities")

    print("\nTop 10 cities by n_individuals:")
    for row in dest.execute("""
        SELECT city_id, name_en, n_individuals, n_birth, n_death, n_both
        FROM city_summary ORDER BY n_individuals DESC LIMIT 10
    """):
        cid, name, n, nb, nd, nboth = row
        print(f"  {cid:10} {name:25} n={n:>6,}  birth={nb:>6,}  death={nd:>6,}  both={nboth:>5,}")

    dest.close()

    size_mb = OUTPUT_PATH.stat().st_size / 1024 / 1024
    print(f"\nWrote {OUTPUT_PATH} ({size_mb:.1f} MB)")
    print("Done! Nothing pushed to Supabase.")


if __name__ == "__main__":
    main()
