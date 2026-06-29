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
from collections import defaultdict
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

    # Polity id -> name (for normalisation / trivial-wrapper detection).
    name_conn = sqlite3.connect(clio_db)
    name_conn.row_factory = sqlite3.Row
    ncur = name_conn.cursor()
    ncur.execute("SELECT id, name FROM polities")
    name_of = {r["id"]: r["name"] for r in ncur}
    name_conn.close()

    def norm(pid):
        """Normalised name — strip the wrapping parens cliopatria uses for metas."""
        n = (name_of.get(pid) or "").strip()
        return n.lstrip("(").rstrip(")").strip()

    # Immediate parent links: a polity points at its level1_id parent.
    immediate_parent = {
        r["polity_id"]: r["level1_id"]
        for r in rows
        if r["is_child"] and r["level1_id"] is not None
    }

    # Children grouped by their immediate parent.
    children = defaultdict(list)
    for pid, par in immediate_parent.items():
        children[par].append(pid)

    # A "trivial wrapper" is a parenthesised meta whose children all normalise to
    # its own name, e.g. "(Roman Empire)" wrapping only "Roman Empire". Such a
    # node is not a meaningful meta level — it must be collapsed so a polity is
    # never both a meta and its own member (BUN-1139 review feedback).
    trivial = set()
    for par, kids in children.items():
        par_norm = norm(par)
        if all(norm(k) == par_norm for k in kids):
            trivial.add(par)

    def effective_parent(pid):
        """Walk up past trivial wrappers to the first real meta (or None)."""
        seen = set()
        cur_p = immediate_parent.get(pid)
        while cur_p is not None and cur_p in trivial and cur_p not in seen:
            seen.add(cur_p)
            cur_p = immediate_parent.get(cur_p)
        return cur_p

    # Build the cleaned parent map, then derive metas + depth from it.
    all_ids = set(immediate_parent) | {
        p for ks in children.values() for p in ks
    } | set(children)
    parent_of = {pid: effective_parent(pid) for pid in all_ids}
    real_meta_ids = {p for p in parent_of.values() if p is not None}

    def depth_of(pid):
        d, seen, cur_p = 0, set(), parent_of.get(pid)
        while cur_p is not None and cur_p not in seen:
            seen.add(cur_p)
            d += 1
            cur_p = parent_of.get(cur_p)
        return d

    mapping = {}
    for pid in all_ids:
        mapping[pid] = {
            "parent_id": parent_of.get(pid),
            "is_meta": pid in real_meta_ids,
            "depth": depth_of(pid),
        }

    n_child = sum(1 for v in mapping.values() if v["parent_id"] is not None)
    n_meta = sum(1 for v in mapping.values() if v["is_meta"])
    print(
        f"  hierarchy rows: {len(mapping)} | with real parent: {n_child} | "
        f"real metas: {n_meta} | collapsed trivial wrappers: {len(trivial)}"
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
    """Reset + set parent_id/is_meta/depth for EVERY Supabase polity.

    We iterate over the live polity ids (not just the hierarchy ids) so that any
    polity not in the hierarchy — or one previously mis-flagged as a trivial
    wrapper — is reset to the default (no parent, not a meta). Only the 3
    hierarchy columns are touched.
    """
    default = {"parent_id": None, "is_meta": False, "depth": 0}
    ids, page, page_size = [], 0, 1000
    while True:
        resp = (
            supabase.table("polities")
            .select("id")
            .range(page * page_size, page * page_size + page_size - 1)
            .execute()
        )
        if not resp.data:
            break
        ids.extend(r["id"] for r in resp.data)
        if len(resp.data) < page_size:
            break
        page += 1

    updated = 0
    for pid in tqdm(ids, desc="Updating polities"):
        vals = mapping.get(pid, default)
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
