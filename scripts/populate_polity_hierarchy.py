"""
BUN-1139 — Populate the meta-polity hierarchy columns on Supabase `polities`.

Reads the polity hierarchy from the AUTHORITATIVE v3 geojson
(`cliopatria_polities_only_v3.geojson`) — NOT the stale cliopatria.db — and sets,
for each polity:
  - parent_id : the immediate meta level above it, or NULL
  - is_meta   : True if it groups >= 2 distinct polities
  - depth     : how many meta levels exist above it

The geojson encodes the hierarchy by NAME:
  - territorial nesting: a POLITY's `MemberOf` is its parent's name
    (e.g. "Kingdom of Bohemia" -> "Holy Roman Empire"), chainable;
  - RELATION entities (alliances/allegiances/personal unions, parenthesised
    names) group the base polities listed in their `Components`.
Names are matched to Supabase polity ids (preferring the real polity over its
parenthesised twin). Walking `parent_id` upward reconstructs the full chain.

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
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from tqdm import tqdm

ROOT = Path(__file__).parent.parent
load_dotenv(ROOT / ".env")

GEOJSON_PATH = Path(
    "/Users/charlesdedampierre/Desktop/Rsearch Folder/cultura/cultura_database/"
    "cliopatria_data/cliopatria_V2/cliopatria_polities_only_v3.geojson"
)
BACKUP_DIR = ROOT / "data" / "backups"


def _norm(name):
    return (name or "").strip().lstrip("(").rstrip(")").strip().lower()


def get_supabase_client():
    import os

    url = os.getenv("SUPABASE_Project_URL")
    key = os.getenv("SUPABASE_SERVICE_KEY")
    if not url or not key:
        raise ValueError("Missing SUPABASE_Project_URL or SUPABASE_SERVICE_KEY in .env")
    from supabase import create_client

    return create_client(url, key)


def build_hierarchy_mapping(geojson_path: Path, polity_rows: list):
    """Return {polity_id: {parent_id, is_meta, depth}} from the v3 geojson.

    `polity_rows` is the live Supabase `polities` (id, name, individuals_count),
    used to resolve geojson names to ids.
    """
    if not geojson_path.exists():
        raise FileNotFoundError(f"v3 geojson not found at {geojson_path}")

    # Name -> candidate ids, classified by parenthesised vs real, with the
    # individuals_count for tie-breaking.
    by_name = defaultdict(list)
    name_of = {}
    for r in polity_rows:
        name_of[r["id"]] = r["name"]
        by_name[_norm(r["name"])].append(
            {
                "id": r["id"],
                "paren": (r["name"] or "").strip().startswith("("),
                "n": r.get("individuals_count") or 0,
            }
        )

    def resolve(name, prefer_paren):
        """Best Supabase id for a geojson name (prefer real polity, else paren)."""
        cands = by_name.get(_norm(name))
        if not cands:
            return None
        cands = sorted(
            cands,
            key=lambda c: (c["paren"] == prefer_paren, c["n"], -c["id"]),
            reverse=True,
        )
        return cands[0]["id"]

    feats = json.load(open(geojson_path))["features"]

    # Collect parent links per child: territorial (MemberOf) and relation
    # (a RELATION's Components). child_id -> {"terr": set, "rel": set}.
    parents = defaultdict(lambda: {"terr": set(), "rel": set()})
    for f in feats:
        p = f["properties"]
        if p.get("MemberOf"):
            cid = resolve(p["Name"], prefer_paren=False)
            pid = resolve(p["MemberOf"], prefer_paren=False)
            if cid is not None and pid is not None and cid != pid:
                parents[cid]["terr"].add(pid)
        if p["Type"] == "RELATION" and p.get("Components"):
            rid = resolve(p["Name"], prefer_paren=True)
            if rid is not None:
                for comp in p["Components"].split(";"):
                    cid = resolve(comp, prefer_paren=False)
                    if cid is not None and cid != rid:
                        parents[cid]["rel"].add(rid)

    # Children grouped by every candidate parent — used to score "meta-ness".
    cand_children = defaultdict(set)
    for cid, ps in parents.items():
        for pid in ps["terr"] | ps["rel"]:
            cand_children[pid].add(cid)

    def n_meta_children(pid):
        own = _norm(name_of.get(pid, ""))
        return len({_norm(name_of.get(c, "")) for c in cand_children[pid]} - {own})

    # Pick ONE parent per child (drill-up is single-parent): prefer a territorial
    # parent, then the candidate that groups the most distinct polities (the major
    # empire / the real meta), tie-break by id.
    def choose(cid):
        ps = parents[cid]
        terr = sorted(ps["terr"], key=lambda x: (n_meta_children(x), -x), reverse=True)
        rel = sorted(ps["rel"], key=lambda x: (n_meta_children(x), -x), reverse=True)
        for pid in terr + rel:
            return pid
        return None

    immediate_parent = {cid: choose(cid) for cid in parents}
    immediate_parent = {c: p for c, p in immediate_parent.items() if p is not None}

    children = defaultdict(list)
    for cid, pid in immediate_parent.items():
        children[pid].append(cid)

    # A REAL meta groups >= 2 distinct polities (by name, excluding its own twin).
    def distinct_children(par):
        own = _norm(name_of.get(par, ""))
        return {_norm(name_of.get(k, "")) for k in children[par] if _norm(name_of.get(k, "")) != own}

    real_meta = {par for par in children if len(distinct_children(par)) >= 2}
    not_meta = set(children) - real_meta

    def effective_parent(pid):
        seen = set()
        cur_p = immediate_parent.get(pid)
        while cur_p is not None and cur_p in not_meta and cur_p not in seen:
            seen.add(cur_p)
            cur_p = immediate_parent.get(cur_p)
        return cur_p

    all_ids = set(immediate_parent) | set(children)
    parent_of = {pid: effective_parent(pid) for pid in all_ids}
    real_meta_ids = {p for p in parent_of.values() if p is not None}

    def depth_of(pid):
        d, seen, cur_p = 0, set(), parent_of.get(pid)
        while cur_p is not None and cur_p not in seen:
            seen.add(cur_p)
            d += 1
            cur_p = parent_of.get(cur_p)
        return d

    mapping = {
        pid: {
            "parent_id": parent_of.get(pid),
            "is_meta": pid in real_meta_ids,
            "depth": depth_of(pid),
        }
        for pid in all_ids
    }

    n_child = sum(1 for v in mapping.values() if v["parent_id"] is not None)
    n_meta = sum(1 for v in mapping.values() if v["is_meta"])
    print(
        f"  source: v3 geojson | mapped polities: {len(mapping)} | "
        f"with parent: {n_child} | real metas: {n_meta} | collapsed: {len(not_meta)}"
    )
    return mapping


def fetch_polities(supabase) -> list:
    """All Supabase polities (id, name, individuals_count) for name resolution."""
    rows, page, page_size = [], 0, 1000
    while True:
        resp = (
            supabase.table("polities")
            .select("id, name, individuals_count")
            .range(page * page_size, page * page_size + page_size - 1)
            .execute()
        )
        if not resp.data:
            break
        rows.extend(resp.data)
        if len(resp.data) < page_size:
            break
        page += 1
    return rows


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

    supabase = get_supabase_client()
    polity_rows = fetch_polities(supabase)
    print("Building hierarchy mapping from v3 geojson ...")
    mapping = build_hierarchy_mapping(GEOJSON_PATH, polity_rows)

    if args.dry_run:
        name_of = {r["id"]: r["name"] for r in polity_rows}
        print("Dry run — no writes. Metas (sample):")
        metas = [pid for pid, v in mapping.items() if v["is_meta"]]
        for pid in metas[:12]:
            kids = [name_of.get(c) for c, v in mapping.items() if v["parent_id"] == pid]
            print(f"  {name_of.get(pid)} ({len(kids)} children): {kids[:6]}")
        print(f"  total metas: {len(metas)}")
        return

    print("Backing up current polities ...")
    backup_polities(supabase)
    print("Applying hierarchy mapping ...")
    apply_mapping(supabase, mapping)
    print("Done.")


if __name__ == "__main__":
    sys.exit(main())
