"""Polity-related API endpoints."""

import json
from fastapi import APIRouter, Query, HTTPException
from typing import Literal
from ..database import get_db
from ..models import (
    ActivePolitiesResponse,
    PolityWithGeometry,
    PolityEvolution,
    EvolutionPoint,
)


router = APIRouter(prefix="/polities", tags=["polities"])


# Which display_mode values to show for each hierarchy level
HIERARCHY_FILTERS = {
    "leaf": ["both", "leaf"],
    "aggregate": ["both", "aggregate"],
}


def _norm_name(name: str | None) -> str:
    """Normalised polity name — drop the wrapping parens cliopatria uses for metas."""
    if not name:
        return ""
    return name.strip().lstrip("(").rstrip(")").strip().lower()


def _ring_area_centroid(ring: list) -> tuple[float, list]:
    """Shoelace area + average-vertex centroid of one polygon ring."""
    if not ring or len(ring) < 3:
        return 0.0, [0.0, 0.0]
    area = 0.0
    for i in range(len(ring) - 1):
        area += ring[i][0] * ring[i + 1][1] - ring[i + 1][0] * ring[i][1]
    cx = sum(c[0] for c in ring) / len(ring)
    cy = sum(c[1] for c in ring) / len(ring)
    return abs(area / 2), [cx, cy]


def _largest_centroid(geometry: dict):
    """Centroid of the LARGEST polygon in a geometry (so a scattered polity like
    the Crown of Aragon centres on its mainland, not a tiny island)."""
    best_area, best_c = -1.0, None
    try:
        if geometry["type"] == "Polygon":
            a, c = _ring_area_centroid(geometry["coordinates"][0])
            return c if a > 0 else None
        if geometry["type"] == "MultiPolygon":
            for poly in geometry["coordinates"]:
                a, c = _ring_area_centroid(poly[0])
                if a > best_area:
                    best_area, best_c = a, c
            return best_c
    except (KeyError, IndexError, TypeError):
        return None
    return None


def _dedupe_children(rows: list[dict]) -> list[dict]:
    """Collapse paren/non-paren twins that share a normalised name.

    e.g. "(Kingdom of the Franks)" + "Kingdom of the Franks" -> one entry.
    Prefer the non-parenthesised name, then the one with more individuals.
    `rows` must contain id, name, and (optionally) individuals_count.
    """
    best: dict[str, dict] = {}
    for r in rows:
        key = _norm_name(r["name"])
        if not key:
            continue
        cur = best.get(key)
        if cur is None:
            best[key] = r
            continue
        # Prefer non-paren, then higher individuals_count, then lower id.
        cand_paren = r["name"].strip().startswith("(")
        cur_paren = cur["name"].strip().startswith("(")
        better = (
            (not cand_paren, r.get("individuals_count") or 0, -r["id"])
            > (not cur_paren, cur.get("individuals_count") or 0, -cur["id"])
        )
        if better:
            best[key] = r
    return list(best.values())


@router.get("/active", response_model=ActivePolitiesResponse)
def get_active_polities(
    year: int = Query(..., description="Year to query"),
    hierarchy: Literal["leaf", "aggregate"] = Query(
        "leaf", description="Hierarchy level: 'leaf' for smaller polities (default), 'aggregate' for larger groupings"
    ),
):
    """Get all polities active at a specific year with their geometries."""
    allowed_modes = HIERARCHY_FILTERS[hierarchy]
    db = get_db()

    # Get polity periods active at this year
    response = db.table("polity_periods").select(
        "id, polity_id, polity_name, from_year, to_year, geometry"
    ).lte("from_year", year).gte("to_year", year).execute()

    period_rows = response.data

    # Get polity IDs to filter by display_mode
    polity_ids = list(set(row["polity_id"] for row in period_rows))

    if not polity_ids:
        return ActivePolitiesResponse(year=year, polities=[])

    # Get polities with matching display_mode
    polities_response = db.table("polities").select(
        "id, name, type, display_mode"
    ).in_("id", polity_ids).in_("display_mode", allowed_modes).execute()

    valid_polity_map = {p["id"]: p for p in polities_response.data}

    polities = []
    for row in period_rows:
        polity_id = row["polity_id"]
        if polity_id not in valid_polity_map:
            continue

        polity = valid_polity_map[polity_id]
        geometry = None
        if row["geometry"]:
            try:
                geometry = json.loads(row["geometry"])
            except json.JSONDecodeError:
                pass

        polities.append(PolityWithGeometry(
            id=polity_id,
            name=polity["name"],
            type=polity["type"],
            from_year=row["from_year"],
            to_year=row["to_year"],
            geometry=geometry
        ))

    return ActivePolitiesResponse(year=year, polities=polities)


@router.get("/{polity_id}/active-subtree", response_model=ActivePolitiesResponse)
def get_active_subtree(
    polity_id: int,
    year: int = Query(..., description="Year to query"),
):
    """Geometries for a meta polity + up to TWO levels of sub-polities active at `year`.

    Used by the map's meta-focus view: drilling UP to a meta renders the meta's
    own territory together with the more granular polities below it — two levels
    deep so nested groupings (e.g. dynasties under a sultanate) are visible too
    (BUN-1139 review). Paren/non-paren duplicates are collapsed.
    """
    db = get_db()

    # Level 1: direct children. Level 2: children of any child that is a meta.
    lvl1 = db.table("polities").select("id, name, type, is_meta, individuals_count").eq(
        "parent_id", polity_id
    ).execute().data
    lvl1_meta_ids = [c["id"] for c in lvl1 if c.get("is_meta")]
    lvl2 = []
    if lvl1_meta_ids:
        lvl2 = db.table("polities").select(
            "id, name, type, is_meta, individuals_count"
        ).in_("parent_id", lvl1_meta_ids).execute().data

    children = _dedupe_children(lvl1 + lvl2)

    meta = db.table("polities").select("id, name, type").eq("id", polity_id).execute().data
    name_by_id = {c["id"]: c["name"] for c in children}
    if meta:
        name_by_id[polity_id] = meta[0]["name"]
    ids = [polity_id] + [c["id"] for c in children]

    period_rows = db.table("polity_periods").select(
        "polity_id, polity_name, from_year, to_year, geometry"
    ).in_("polity_id", ids).lte("from_year", year).gte("to_year", year).execute().data

    polities = []
    seen_norm: set[str] = set()
    for row in period_rows:
        pid = row["polity_id"]
        disp_name = name_by_id.get(pid, row["polity_name"])
        # Guard against the same normalised name slipping in via a second period.
        norm = _norm_name(disp_name)
        if pid != polity_id and norm in seen_norm:
            continue
        seen_norm.add(norm)

        geometry = None
        if row["geometry"]:
            try:
                geometry = json.loads(row["geometry"])
            except json.JSONDecodeError:
                pass
        polities.append(PolityWithGeometry(
            id=pid,
            name=disp_name,
            type="meta" if pid == polity_id else "leaf",
            from_year=row["from_year"],
            to_year=row["to_year"],
            geometry=geometry,
        ))

    return ActivePolitiesResponse(year=year, polities=polities)


@router.get("/{polity_id}/evolution", response_model=PolityEvolution)
def get_polity_evolution(polity_id: int):
    """Get individual count per 25-year period for a polity."""
    db = get_db()

    # Get polity info
    polity_response = db.table("polities").select("id, name").eq("id", polity_id).execute()

    if not polity_response.data:
        raise HTTPException(status_code=404, detail="Polity not found")

    polity = polity_response.data[0]

    # Get polity lifespan from periods
    periods_response = db.table("polity_periods").select(
        "from_year, to_year"
    ).eq("polity_id", polity_id).execute()

    from_year = None
    to_year = None
    if periods_response.data:
        from_year = min(p["from_year"] for p in periods_response.data)
        to_year = max(p["to_year"] for p in periods_response.data)

    # Get evolution data
    evolution_response = db.table("evolution_cache").select(
        "year, count"
    ).eq("polity_id", polity_id).order("year").execute()

    evolution = [
        EvolutionPoint(year=row["year"], count=row["count"])
        for row in evolution_response.data
    ]

    return PolityEvolution(
        polity_id=polity_id,
        polity_name=polity["name"],
        from_year=from_year,
        to_year=to_year,
        evolution=evolution
    )


@router.get("/search")
def search_polities(
    q: str = Query(..., min_length=1, description="Search query for polity name"),
    limit: int = Query(10, ge=1, le=50, description="Maximum number of results"),
):
    """Search polities by name (case-insensitive partial match).

    Returns both granular polities and meta levels. A meta hit is flagged with
    ``is_meta`` so the UI can focus it and reveal the more granular levels
    around it (BUN-1139).
    """
    db = get_db()

    # Use ilike for case-insensitive partial match across all hierarchy levels.
    response = db.table("polities").select(
        "id, name, type, parent_id, is_meta, depth, individuals_count"
    ).ilike("name", f"%{q}%").limit(limit * 3).execute()

    # Collapse paren/non-paren twins, preferring the meta, then the non-paren,
    # then the more-populated polity (BUN-1139 review: no duplicate names).
    deduped: dict[str, dict] = {}
    for p in response.data:
        key = _norm_name(p["name"])
        if not key:
            continue
        cur = deduped.get(key)
        if cur is None:
            deduped[key] = p
            continue
        cand = (p.get("is_meta", False), not p["name"].strip().startswith("("),
                p.get("individuals_count") or 0, -p["id"])
        curr = (cur.get("is_meta", False), not cur["name"].strip().startswith("("),
                cur.get("individuals_count") or 0, -cur["id"])
        if cand > curr:
            deduped[key] = p
    response_data = list(deduped.values())[:limit]

    # Get centroid and date range for each polity from their periods
    results = []
    for polity in response_data:
        # Get geometry and dates for centroid calculation
        period_response = db.table("polity_periods").select(
            "geometry, from_year, to_year"
        ).eq("polity_id", polity["id"]).execute()

        centroid = None
        from_year = None
        to_year = None

        if period_response.data:
            # Get date range from all periods
            from_year = min(p["from_year"] for p in period_response.data if p["from_year"] is not None)
            to_year = max(p["to_year"] for p in period_response.data if p["to_year"] is not None)

            # Centroid from the largest polygon of the largest period geometry.
            for period in period_response.data:
                if period["geometry"]:
                    try:
                        c = _largest_centroid(json.loads(period["geometry"]))
                        if c:
                            centroid = c
                            break
                    except json.JSONDecodeError:
                        pass

        results.append({
            "id": polity["id"],
            "name": polity["name"],
            "from_year": from_year,
            "to_year": to_year,
            "centroid": centroid,
            "parent_id": polity.get("parent_id"),
            "is_meta": polity.get("is_meta", False),
            "depth": polity.get("depth", 0),
        })

    # Surface meta levels first so "search a meta" lands on the meta itself.
    results.sort(key=lambda r: (not r["is_meta"], r["name"].lower()))
    return {"results": results}


@router.get("/{polity_id}")
def get_polity(polity_id: int):
    """Get polity details."""
    db = get_db()

    polity_response = db.table("polities").select("*").eq("id", polity_id).execute()

    if not polity_response.data:
        raise HTTPException(status_code=404, detail="Polity not found")

    polity = polity_response.data[0]

    # Get lifespan from periods
    periods_response = db.table("polity_periods").select(
        "from_year, to_year"
    ).eq("polity_id", polity_id).execute()

    from_year = None
    to_year = None
    if periods_response.data:
        from_year = min(p["from_year"] for p in periods_response.data)
        to_year = max(p["to_year"] for p in periods_response.data)

    # Hierarchy (BUN-1139): immediate meta parent + direct children, so the UI
    # can offer "go up to the meta level" and list the granular levels below.
    parent_id = polity.get("parent_id")
    parent_name = None
    if parent_id is not None:
        parent_resp = db.table("polities").select("name").eq("id", parent_id).execute()
        if parent_resp.data:
            parent_name = parent_resp.data[0]["name"]

    children_resp = db.table("polities").select(
        "id, name, individuals_count"
    ).eq("parent_id", polity_id).execute()
    children_deduped = _dedupe_children(children_resp.data)
    children_deduped.sort(key=lambda c: _norm_name(c["name"]))

    # Per-child active range, so clicking a sub-polity can jump the timeline to
    # its creation year (BUN-1139 review: inactive children did nothing on click).
    child_ids = [c["id"] for c in children_deduped]
    child_from: dict[int, int] = {}
    child_to: dict[int, int] = {}
    if child_ids:
        cp = db.table("polity_periods").select(
            "polity_id, from_year, to_year"
        ).in_("polity_id", child_ids).execute().data
        for row in cp:
            pid = row["polity_id"]
            if row["from_year"] is not None:
                child_from[pid] = min(child_from.get(pid, row["from_year"]), row["from_year"])
            if row["to_year"] is not None:
                child_to[pid] = max(child_to.get(pid, row["to_year"]), row["to_year"])
    children = [
        {
            "id": c["id"],
            "name": c["name"],
            "from_year": child_from.get(c["id"]),
            "to_year": child_to.get(c["id"]),
        }
        for c in children_deduped
    ]

    return {
        "id": polity["id"],
        "name": polity["name"],
        "type": polity["type"],
        "wikipedia_url": polity["wikipedia_url"],
        "wikidata_id": polity["wikidata_id"],
        "individuals_count": polity["individuals_count"],
        "from_year": from_year,
        "to_year": to_year,
        "parent_id": parent_id,
        "parent_name": parent_name,
        "is_meta": polity.get("is_meta", False),
        "depth": polity.get("depth", 0),
        "children": children,
    }
