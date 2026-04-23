"""City-related API endpoints."""

from fastapi import APIRouter, Query, HTTPException
from ..database import get_db
from ..models import PolityTopCities, City


router = APIRouter(prefix="/cities", tags=["cities"])


@router.get("/polity/{polity_id}", response_model=PolityTopCities)
def get_polity_top_cities(
    polity_id: int,
    limit: int = Query(500, ge=1, le=5000, description="Number of cities to return"),
    min_count: int = Query(1, ge=1, description="Minimum individual count to include"),
):
    """Get top cities by individual count for a polity."""
    db = get_db()

    # Verify polity exists
    polity_check = db.table("polities").select("id").eq("id", polity_id).execute()
    if not polity_check.data:
        raise HTTPException(status_code=404, detail="Polity not found")

    # Get top cities from cache (filter out NULL lat/lon and below min_count)
    response = db.table("top_cities_cache").select(
        "city_id, city_name, lat, lon, individual_count"
    ).eq("polity_id", polity_id).gte(
        "individual_count", min_count
    ).not_.is_("lat", "null").not_.is_("lon", "null").order(
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


@router.get("/polity/{polity_id}/dynamic")
def get_polity_cities_dynamic(
    polity_id: int,
    year: int = Query(..., description="Center year for the 25-year window"),
    limit: int = Query(200, ge=1, le=1000, description="Maximum cities to return"),
):
    """Get cities with individual counts for a specific 25-year window.

    Counts individuals whose impact_date falls within [year-12, year+12].
    This allows visualizing how the "center of gravity" shifts over time.
    """
    db = get_db()

    # Define the 25-year window
    year_start = year - 12
    year_end = year + 12

    # Get individuals in this polity within the year range
    # Only select city IDs (minimal data transfer)
    individuals = db.table("individuals_light").select(
        "birthcity_id, deathcity_id"
    ).eq("polity_id", polity_id).gte(
        "impact_date_raw", year_start
    ).lte(
        "impact_date_raw", year_end
    ).limit(10000).execute()  # Cap at 10k individuals for performance

    if not individuals.data:
        return {"polity_id": polity_id, "year": year, "cities": []}

    # Count individuals per city (birth city priority, death city fallback)
    city_counts: dict[str, int] = {}
    for ind in individuals.data:
        # Use birth city if available, otherwise death city
        city_id = ind.get("birthcity_id") or ind.get("deathcity_id")
        if city_id:
            city_counts[city_id] = city_counts.get(city_id, 0) + 1

    if not city_counts:
        return {"polity_id": polity_id, "year": year, "cities": []}

    # Sort by count and take top cities
    top_city_ids = sorted(city_counts.keys(), key=lambda x: -city_counts[x])[:limit]

    # Get city details (coordinates, names) only for top cities.
    # Filter to urban settlements — non-urban places (parishes, minor localities,
    # etc.) should not appear on the map.
    cities_response = db.table("cities").select(
        "id, name_en, lat, lon"
    ).in_("id", top_city_ids).eq("is_urban_settlement", True).not_.is_(
        "lat", "null"
    ).not_.is_("lon", "null").execute()

    # Build result
    cities = []
    for city in cities_response.data:
        city_id = city["id"]
        cities.append({
            "city_id": city_id,
            "name": city["name_en"],
            "lat": city["lat"],
            "lon": city["lon"],
            "count": city_counts.get(city_id, 0),
        })

    # Sort by count descending
    cities.sort(key=lambda x: -x["count"])

    return {"polity_id": polity_id, "year": year, "cities": cities}


@router.get("/search")
def search_cities(
    q: str = Query(..., min_length=2, description="Search query"),
    limit: int = Query(20, ge=1, le=50, description="Number of results to return"),
):
    """Search cities by name across all polities.

    Returns unique cities, each linked to the earliest LEAF polity where the city first appeared.
    Parent polities (names starting with '(') are excluded - only leaf polities shown on the map.
    Cities with exact name matches are prioritized, then cities containing the query.
    """
    db = get_db()

    # Search cities by name (case-insensitive partial match)
    # Get more results to account for deduplication and filtering
    response = db.table("top_cities_cache").select(
        "city_id, city_name, lat, lon, individual_count, polity_id, first_individual_year, peak_year"
    ).ilike("city_name", f"%{q}%").not_.is_("lat", "null").not_.is_("lon", "null").order(
        "individual_count", desc=True
    ).limit(limit * 20).execute()

    if not response.data:
        return {"results": []}

    # Get polity info (name, from_year) for all polities in results
    polity_ids = list(set(row["polity_id"] for row in response.data))

    # Get polity names to filter out parent polities (names starting with '(')
    polities_response = db.table("polities").select(
        "id, name"
    ).in_("id", polity_ids).execute()

    # Build a set of leaf polity IDs (names NOT starting with '(') and their names
    leaf_polity_ids = set()
    polity_names: dict[int, str] = {}
    for p in polities_response.data:
        if p["name"] and not p["name"].startswith("("):
            leaf_polity_ids.add(p["id"])
            polity_names[p["id"]] = p["name"]

    # Get periods for leaf polities only
    periods_response = db.table("polity_periods").select(
        "polity_id, from_year, to_year"
    ).in_("polity_id", list(leaf_polity_ids)).execute()

    # Aggregate: min(from_year) and max(to_year) per leaf polity
    polity_from_years: dict[int, int | None] = {}
    polity_to_years: dict[int, int | None] = {}
    for p in periods_response.data:
        pid = p["polity_id"]
        fy = p["from_year"]
        ty = p["to_year"]
        if fy is not None:
            cur = polity_from_years.get(pid)
            if cur is None or fy < cur:
                polity_from_years[pid] = fy
        if ty is not None:
            cur = polity_to_years.get(pid)
            if cur is None or ty > cur:
                polity_to_years[pid] = ty

    # Deduplicate by city_id, keeping the polity with the MOST individuals
    city_map: dict[str, dict] = {}
    query_lower = q.lower()

    for row in response.data:
        polity_id = row["polity_id"]

        # Skip parent polities (not leaf)
        if polity_id not in leaf_polity_ids:
            continue

        city_id = row["city_id"]
        city_name = row["city_name"]
        individual_count = row["individual_count"]
        polity_from_year = polity_from_years.get(polity_id)
        polity_to_year = polity_to_years.get(polity_id)
        polity_name = polity_names.get(polity_id, "Unknown")

        # Check if this is an exact match or starts with query
        name_lower = city_name.lower()
        is_exact = name_lower == query_lower
        starts_with = name_lower.startswith(query_lower)

        # Get first_individual_year from cache (when city first appears with an individual)
        first_individual_year = row.get("first_individual_year") or polity_from_year
        # peak_year = year where this city has the most individuals (25-year window)
        peak_year = row.get("peak_year")

        entry = {
            "city_id": city_id,
            "name": city_name,
            "lat": row["lat"],
            "lon": row["lon"],
            "count": individual_count,
            "polity_id": polity_id,
            "polity_name": polity_name,
            "polity_from_year": polity_from_year,
            "polity_to_year": polity_to_year,
            "first_individual_year": first_individual_year,
            "peak_year": peak_year,
            "_is_exact": is_exact,
            "_starts_with": starts_with,
        }

        if city_id not in city_map:
            city_map[city_id] = entry
        elif individual_count > city_map[city_id]["count"]:
            # Keep the polity with more individuals
            city_map[city_id] = entry

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


@router.get("/polity/{polity_id}/individuals-cities")
def get_polity_individuals_cities(
    polity_id: int,
):
    """Get all individuals with their city and impact year for client-side dynamic computation.

    Returns minimal data needed to compute dynamic city counts on the frontend.
    """
    db = get_db()

    # Get all individuals for this polity with city info
    response = db.table("individuals_light").select(
        "birthcity_id, deathcity_id, impact_date_raw"
    ).eq("polity_id", polity_id).not_.is_(
        "impact_date_raw", "null"
    ).execute()

    if not response.data:
        return {"polity_id": polity_id, "individuals": []}

    # Simplify: just return city_id (birth or death) and year
    individuals = []
    for ind in response.data:
        city_id = ind.get("birthcity_id") or ind.get("deathcity_id")
        if city_id and ind.get("impact_date_raw") is not None:
            individuals.append({
                "c": city_id,  # city_id (short key for smaller payload)
                "y": ind["impact_date_raw"],  # year
            })

    return {"polity_id": polity_id, "individuals": individuals}


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
