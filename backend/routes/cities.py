"""City-related API endpoints."""

from fastapi import APIRouter, Query, HTTPException
from ..database import get_db
from ..models import PolityTopCities, City


router = APIRouter(prefix="/cities", tags=["cities"])


@router.get("/polity/{polity_id}", response_model=PolityTopCities)
def get_polity_top_cities(
    polity_id: int,
    limit: int = Query(100, ge=1, le=500, description="Number of cities to return"),
):
    """Get top cities by individual count for a polity."""
    db = get_db()

    # Verify polity exists
    polity_check = db.table("polities").select("id").eq("id", polity_id).execute()
    if not polity_check.data:
        raise HTTPException(status_code=404, detail="Polity not found")

    # Get top cities from cache (filter out NULL lat/lon)
    response = db.table("top_cities_cache").select(
        "city_id, city_name, lat, lon, individual_count"
    ).eq("polity_id", polity_id).not_.is_("lat", "null").not_.is_("lon", "null").order(
        "individual_count", desc=True
    ).limit(limit).execute()

    cities = [
        City(
            city_id=row["city_id"],
            name=row["city_name"],
            lat=row["lat"],
            lon=row["lon"],
            count=row["individual_count"]
        )
        for row in response.data
    ]

    return PolityTopCities(polity_id=polity_id, cities=cities)


@router.get("/search")
def search_cities(
    q: str = Query(..., min_length=2, description="Search query"),
    limit: int = Query(20, ge=1, le=50, description="Number of results to return"),
):
    """Search cities by name across all polities.

    Returns unique cities, each linked to the earliest polity where the city first appeared.
    Cities with exact name matches are prioritized, then cities containing the query.
    """
    db = get_db()

    # Search cities by name (case-insensitive partial match)
    # Get more results to account for deduplication
    response = db.table("top_cities_cache").select(
        "city_id, city_name, lat, lon, individual_count, polity_id"
    ).ilike("city_name", f"%{q}%").not_.is_("lat", "null").not_.is_("lon", "null").order(
        "individual_count", desc=True
    ).limit(limit * 10).execute()

    if not response.data:
        return {"results": []}

    # Get polity info (from_year) from polity_periods for all polities in results
    polity_ids = list(set(row["polity_id"] for row in response.data))
    periods_response = db.table("polity_periods").select(
        "polity_id, from_year"
    ).in_("polity_id", polity_ids).execute()

    # Get the minimum from_year for each polity
    polity_years: dict[int, int | None] = {}
    for p in periods_response.data:
        pid = p["polity_id"]
        year = p["from_year"]
        if pid not in polity_years or (year is not None and (polity_years[pid] is None or year < polity_years[pid])):
            polity_years[pid] = year

    # Deduplicate by city_id, keeping the entry with the earliest polity_from_year
    city_map: dict[str, dict] = {}
    query_lower = q.lower()

    for row in response.data:
        city_id = row["city_id"]
        city_name = row["city_name"]
        polity_from_year = polity_years.get(row["polity_id"])

        # Check if this is an exact match or starts with query
        name_lower = city_name.lower()
        is_exact = name_lower == query_lower
        starts_with = name_lower.startswith(query_lower)

        if city_id not in city_map:
            # First occurrence of this city
            city_map[city_id] = {
                "city_id": city_id,
                "name": city_name,
                "lat": row["lat"],
                "lon": row["lon"],
                "count": row["individual_count"],
                "polity_id": row["polity_id"],
                "polity_from_year": polity_from_year,
                "_is_exact": is_exact,
                "_starts_with": starts_with,
            }
        else:
            # Check if this polity is earlier
            existing_year = city_map[city_id]["polity_from_year"]
            if polity_from_year is not None and (existing_year is None or polity_from_year < existing_year):
                city_map[city_id] = {
                    "city_id": city_id,
                    "name": city_name,
                    "lat": row["lat"],
                    "lon": row["lon"],
                    "count": row["individual_count"],
                    "polity_id": row["polity_id"],
                    "polity_from_year": polity_from_year,
                    "_is_exact": is_exact,
                    "_starts_with": starts_with,
                }

    # Sort: exact matches first, then starts-with, then by count
    def sort_key(x):
        return (
            not x.get("_is_exact", False),      # Exact matches first (False < True)
            not x.get("_starts_with", False),   # Then starts-with
            -x["count"],                         # Then by count descending
        )

    sorted_results = sorted(city_map.values(), key=sort_key)[:limit]

    # Remove internal sorting keys
    results = [
        {k: v for k, v in r.items() if not k.startswith("_")}
        for r in sorted_results
    ]

    return {"results": results}


@router.get("/{city_id}")
def get_city(city_id: str):
    """Get city details."""
    db = get_db()

    response = db.table("cities").select("*").eq("id", city_id).execute()

    if not response.data:
        raise HTTPException(status_code=404, detail="City not found")

    row = response.data[0]

    return {
        "id": row["id"],
        "name_en": row["name_en"],
        "lat": row["lat"],
        "lon": row["lon"],
        "iso_country_name": row["iso_country_name"],
    }
