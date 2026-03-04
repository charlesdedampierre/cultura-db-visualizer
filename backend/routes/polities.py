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
    """Search polities by name (case-insensitive partial match)."""
    db = get_db()

    # Use ilike for case-insensitive partial match
    response = db.table("polities").select(
        "id, name, type"
    ).ilike("name", f"%{q}%").limit(limit).execute()

    # Get centroid for each polity from their periods
    results = []
    for polity in response.data:
        # Get geometry for centroid calculation
        period_response = db.table("polity_periods").select(
            "geometry"
        ).eq("polity_id", polity["id"]).limit(1).execute()

        centroid = None
        if period_response.data and period_response.data[0]["geometry"]:
            try:
                geometry = json.loads(period_response.data[0]["geometry"])
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
            except (json.JSONDecodeError, KeyError, IndexError):
                pass

        results.append({
            "id": polity["id"],
            "name": polity["name"],
            "type": polity["type"],
            "centroid": centroid,
        })

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

    return {
        "id": polity["id"],
        "name": polity["name"],
        "type": polity["type"],
        "wikipedia_url": polity["wikipedia_url"],
        "wikidata_id": polity["wikidata_id"],
        "individuals_count": polity["individuals_count"],
        "from_year": from_year,
        "to_year": to_year,
    }
