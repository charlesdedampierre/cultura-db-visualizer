"""
BUN-1139 — Populate the meta-polity hierarchy columns on Supabase `polities`.

Reads the polity hierarchy from cliopatria.db and sets, for each polity:
  - parent_id : the immediate meta level above it (level1_id), or NULL
  - is_meta   : True if this polity is itself a parent of others (is_parent)
  - depth     : how many meta levels exist above it (0-3)

Walking `parent_id` upward reconstructs the full chain (leaf -> meta -> meta-of-meta).

Reversible by design:
  - Only UPDATEs the three new columns; never wipes/re-inserts rows.
  - Backs up the current `polities` rows (incl. the new columns) to a local
    JSON before writing, so `--restore` can put them back.

Usage:
    python scripts/populate_polity_hierarchy.py --dry-run   # validate only, no write
    python scripts/populate_polity_hierarchy.py             # backup + write
    python scripts/populate_polity_hierarchy.py --restore <backup.json>

Run the additive migration first:
    supabase/migrations/20260629120000_add_polity_hierarchy.sql

Env (.env): SUPABASE_Project_URL, SUPABASE_SERVICE_KEY
"""

import argparse
import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from tqdm import tqdm

ROOT = Path(__file__).parent.parent
load_dotenv(ROOT / ".env")

CLIO_DB_PATH = Path(
    "/Users/charlesdedampierre/Desktop/Rsearch Folder/cultura/cultura_database/"
    "cliopatria_data/processing/data/cliopatria.db"
)
BACKUP_DIR = ROOT / "data" / "backups"


def get_supabase_client():
    import os

    url = os.getenv("SUPABASE_Project_URL")
    key = os.getenv("SUPABASE_SERVICE_KEY")
    if not url or not key:
        raise ValueError("Missing SUPABASE_Project_URL or SUPABASE_SERVICE_KEY in .env")
    from supabase import create_client

    return create_client(url, key)


def build_hierarchy_mapping(clio_db: Path):
    """Return {polity_id: {parent_id, is_meta, depth}} from cliopatria.db."""
    if not clio_db.exists():
        raise FileNotFoundError(f"cliopatria.db not found at {clio_db}")

    conn = sqlite3.connect(clio_db)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(
        """
        SELECT polity_id, polity_name,
               level1_id, level2_id, level3_id,
               depth, is_parent, is_child
        FROM polity_hierarchy_levels
        """
    )
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()

    mapping = {}
    ancestors = {}  # polity_id -> [level1_id, level2_id, level3_id] (non-null)
    for r in rows:
        pid = r["polity_id"]
        parent_id = r["level1_id"] if r["is_child"] else None
        mapping[pid] = {
            "parent_id": parent_id,
            "is_meta": bool(r["is_parent"]),
            "depth": r["depth"] or 0,
        }
        ancestors[pid] = [
            r[k] for k in ("level1_id", "level2_id", "level3_id") if r[k] is not None
        ]

    # Validate: walking parent_id upward should reproduce the level2/level3 chain.
    mismatches = 0
    for pid, anc in ancestors.items():
        if len(anc) <= 1:
            continue
        walked = []
        cur_pid = mapping[pid]["parent_id"]
        seen = set()
        while cur_pid is not None and cur_pid not in seen and len(walked) < 5:
            seen.add(cur_pid)
            walked.append(cur_pid)
            nxt = mapping.get(cur_pid, {}).get("parent_id")
            cur_pid = nxt
        # Compare the distinct expected ancestors vs the walked chain (order-tolerant
        # on duplicates — some rows repeat the top level in level2/level3).
        expected = []
        for a in anc:
            if a not in expected:
                expected.append(a)
        if expected[: len(walked)] != walked[: len(expected)] and set(walked) != set(
            expected
        ):
            mismatches += 1
    if mismatches:
        print(
            f"  ! {mismatches} polities where parent_id walk != level2/3 chain "
            f"(kept parent_id = level1_id; deeper levels via recursion may differ)"
        )

    n_child = sum(1 for v in mapping.values() if v["parent_id"] is not None)
    n_meta = sum(1 for v in mapping.values() if v["is_meta"])
    print(
        f"  hierarchy rows: {len(mapping)} | with parent: {n_child} | "
        f"meta (is_parent): {n_meta}"
    )
    return mapping


def backup_polities(supabase) -> Path:
    """Dump current `polities` rows (all columns) to a timestamped JSON."""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    rows, page, page_size = [], 0, 1000
    while True:
        resp = (
            supabase.table("polities")
            .select("id, parent_id, is_meta, depth")
            .range(page * page_size, page * page_size + page_size - 1)
            .execute()
        )
        if not resp.data:
            break
        rows.extend(resp.data)
        if len(resp.data) < page_size:
            break
        page += 1
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = BACKUP_DIR / f"polities_hierarchy_backup_{stamp}.json"
    path.write_text(json.dumps(rows, indent=2))
    print(f"  backed up {len(rows)} polity rows -> {path}")
    return path


def apply_mapping(supabase, mapping: dict):
    """UPDATE parent_id/is_meta/depth for each polity. Only touches the 3 columns."""
    items = list(mapping.items())
    updated = 0
    for pid, vals in tqdm(items, desc="Updating polities"):
        supabase.table("polities").update(
            {
                "parent_id": vals["parent_id"],
                "is_meta": vals["is_meta"],
                "depth": vals["depth"],
            }
        ).eq("id", pid).execute()
        updated += 1
    print(f"  updated {updated} polities")


def restore(supabase, backup_path: Path):
    rows = json.loads(Path(backup_path).read_text())
    for r in tqdm(rows, desc="Restoring polities"):
        supabase.table("polities").update(
            {
                "parent_id": r.get("parent_id"),
                "is_meta": r.get("is_meta", False),
                "depth": r.get("depth", 0),
            }
        ).eq("id", r["id"]).execute()
    print(f"  restored {len(rows)} polity rows from {backup_path}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="build + validate, no write")
    ap.add_argument("--restore", metavar="BACKUP_JSON", help="restore from a backup file")
    args = ap.parse_args()

    if args.restore:
        supabase = get_supabase_client()
        restore(supabase, Path(args.restore))
        return

    print("Building hierarchy mapping from cliopatria.db ...")
    mapping = build_hierarchy_mapping(CLIO_DB_PATH)

    if args.dry_run:
        print("Dry run — no writes. Sample:")
        for pid, v in list(mapping.items())[:8]:
            print("  ", pid, v)
        return

    supabase = get_supabase_client()
    print("Backing up current polities ...")
    backup_polities(supabase)
    print("Applying hierarchy mapping ...")
    apply_mapping(supabase, mapping)
    print("Done.")


if __name__ == "__main__":
    sys.exit(main())
