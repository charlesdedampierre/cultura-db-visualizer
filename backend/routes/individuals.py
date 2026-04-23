"""Individual-related API endpoints."""

import logging
from fastapi import APIRouter, Query, HTTPException
from typing import Literal
from ..database import get_db
from ..models import PaginatedIndividuals, Individual

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/individuals", tags=["individuals"])


@router.get("/polity/{polity_id}", response_model=PaginatedIndividuals)
def get_polity_individuals(
    polity_id: int,
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(50, ge=1, le=200, description="Items per page"),
    sort: Literal["sitelinks_count", "impact_date"] = Query(
        "sitelinks_count", description="Sort field"
    ),
    order: Literal["asc", "desc"] = Query("desc", description="Sort order"),
    impact_year: int | None = Query(None, description="Filter by impact year bucket"),
    occupation: str | None = Query(None, description="Filter by occupation"),
    name_search: str | None = Query(None, description="Search by name (case-insensitive)"),
):
    """Get paginated list of individuals for a polity."""
    db = get_db()

    # Verify polity exists
    polity_check = db.table("polities").select("id").eq("id", polity_id).execute()
    if not polity_check.data:
        raise HTTPException(status_code=404, detail="Polity not found")

    # Build query
    query = db.table("individuals_light").select(
        "wikidata_id, name_en, occupations_en, sitelinks_count, impact_date, impact_date_raw",
        count="exact"
    ).eq("polity_id", polity_id).not_.is_("impact_date", "null")

    if impact_year is not None:
        # The evolution chart plots 25-year buckets (floor_to_25). `impact_date`
        # stores that bucket; `impact_date_raw` is the exact year. Filter on
        # the bucket so clicking a point returns every individual in the
        # [impact_year, impact_year + 24] window.
        query = query.eq("impact_date", impact_year)

    if name_search is not None and name_search.strip():
        query = query.ilike("name_en", f"%{name_search.strip()}%")

    if occupation is not None:
        logger.info(f"Filtering by occupation: {occupation}")
        # Use ilike for pattern matching (Supabase/PostgreSQL)
        query = query.or_(
            f"occupations_en.eq.{occupation},"
            f"occupations_en.ilike.{occupation}; %,"
            f"occupations_en.ilike.%; {occupation}; %,"
            f"occupations_en.ilike.%; {occupation}"
        )

    # Apply sorting
    ascending = order == "asc"
    query = query.order(sort, desc=not ascending)

    # Apply pagination
    offset = (page - 1) * limit
    query = query.range(offset, offset + limit - 1)

    # Execute
    response = query.execute()

    total = response.count if response.count else 0

    individuals = [
        Individual(
            wikidata_id=row["wikidata_id"],
            name_en=row["name_en"],
            occupations_en=row["occupations_en"],
            sitelinks_count=row["sitelinks_count"],
            impact_date=row["impact_date"],
            impact_date_raw=row["impact_date_raw"]
        )
        for row in response.data
    ]

    return PaginatedIndividuals(
        polity_id=polity_id,
        total=total,
        page=page,
        limit=limit,
        individuals=individuals
    )


@router.get("/{wikidata_id}")
def get_individual(wikidata_id: str):
    """Get individual details."""
    db = get_db()

    # Get individual (may have multiple rows for different polities, just take first)
    response = db.table("individuals_light").select(
        "wikidata_id, name_en, occupations_en, sitelinks_count, impact_date, birthcity_id, deathcity_id"
    ).eq("wikidata_id", wikidata_id).limit(1).execute()

    if not response.data:
        raise HTTPException(status_code=404, detail="Individual not found")

    row = response.data[0]

    # Get birth city info if available
    birthcity = None
    if row["birthcity_id"]:
        bc_response = db.table("cities").select(
            "name_en, lat, lon"
        ).eq("id", row["birthcity_id"]).execute()

        if bc_response.data:
            bc = bc_response.data[0]
            birthcity = {
                "id": row["birthcity_id"],
                "name": bc["name_en"],
                "lat": bc["lat"],
                "lon": bc["lon"]
            }

    # Get death city info if available
    deathcity = None
    if row["deathcity_id"]:
        dc_response = db.table("cities").select(
            "name_en, lat, lon"
        ).eq("id", row["deathcity_id"]).execute()

        if dc_response.data:
            dc = dc_response.data[0]
            deathcity = {
                "id": row["deathcity_id"],
                "name": dc["name_en"],
                "lat": dc["lat"],
                "lon": dc["lon"]
            }

    return {
        "wikidata_id": row["wikidata_id"],
        "name_en": row["name_en"],
        "occupations_en": row["occupations_en"],
        "sitelinks_count": row["sitelinks_count"],
        "impact_date": row["impact_date"],
        "birthcity": birthcity,
        "deathcity": deathcity,
        "wikidata_url": f"https://www.wikidata.org/wiki/{row['wikidata_id']}"
    }
