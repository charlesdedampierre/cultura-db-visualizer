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
    """Geometries for a meta polity + its direct children active at `year`.

    Used by the map's meta-focus view: when the user drills UP to a meta level
    we render the meta's own territory together with the more granular polities
    one level below it (per BUN-1139). Drilling is one level at a time — a child
    that is itself a meta can be focused in turn.
    """
    db = get_db()

    children = db.table("polities").select("id, name, type").eq(
        "parent_id", polity_id
    ).execute().data
    child_ids = [c["id"] for c in children]
    name_by_id = {c["id"]: c["name"] for c in children}

    # Include the meta itself.
    meta = db.table("polities").select("id, name, type").eq("id", polity_id).execute().data
    if meta:
        name_by_id[polity_id] = meta[0]["name"]
    ids = [polity_id] + child_ids

    period_rows = db.table("polity_periods").select(
        "polity_id, polity_name, from_year, to_year, geometry"
    ).in_("polity_id", ids).lte("from_year", year).gte("to_year", year).execute().data

    polities = []
    for row in period_rows:
        geometry = None
        if row["geometry"]:
            try:
                geometry = json.loads(row["geometry"])
            except json.JSONDecodeError:
                pass
        pid = row["polity_id"]
        polities.append(PolityWithGeometry(
            id=pid,
            name=name_by_id.get(pid, row["polity_name"]),
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
        "id, name, type, parent_id, is_meta, depth"
    ).ilike("name", f"%{q}%").limit(limit).execute()

    # Get centroid and date range for each polity from their periods
    results = []
    for polity in response.data:
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

            # Get centroid from first period with geometry
            for period in period_response.data:
                if period["geometry"]:
                    try:
                        geometry = json.loads(period["geometry"])
                        # Calculate rough centroid from first coordinate
                        if geometry["type"] == "Polygon":
                            coords = geometry["coordinates"][0]
                            centroid = [
                                sum(c[0] for c in coords) / len(coords),
                                sum(c[1] for c in coords) / len(coords),
                            ]
                        elif geometry["type"] == "MultiPolygon":
                            first_poly = geometry["coordinates"][0][0]
                            centroid = [
                                sum(c[0] for c in first_poly) / len(first_poly),
                                sum(c[1] for c in first_poly) / len(first_poly),
                            ]
                        break
                    except (json.JSONDecodeError, KeyError, IndexError):
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

    children_resp = db.table("polities").select("id, name").eq(
        "parent_id", polity_id
    ).order("name").execute()
    children = [{"id": c["id"], "name": c["name"]} for c in children_resp.data]

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
