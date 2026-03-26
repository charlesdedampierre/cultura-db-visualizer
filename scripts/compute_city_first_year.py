"""
Compute the earliest individual year for each city-polity combination.
This pre-computes the data needed for the city search feature.

Run this script to populate first_individual_year in top_cities_cache.
"""

import os
import sys

# Change to project root directory
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(project_root)
sys.path.insert(0, project_root)

from dotenv import load_dotenv
load_dotenv()

from tqdm import tqdm
from backend.database import get_db


def main():
    db = get_db()

    print("Fetching all city-polity pairs from top_cities_cache...")

    # Get all unique city-polity pairs
    response = db.table("top_cities_cache").select("city_id, polity_id").execute()
    pairs = [(r["city_id"], r["polity_id"]) for r in response.data]

    print(f"Found {len(pairs)} city-polity pairs")
    print("Computing earliest individual year for each pair...")

    updates = []

    for city_id, polity_id in tqdm(pairs):
        # Get earliest individual from this city in this polity
        earliest = db.table("individuals_light").select(
            "impact_date_raw"
        ).eq("polity_id", polity_id).eq(
            "birthcity_id", city_id
        ).not_.is_("impact_date_raw", "null").order(
            "impact_date_raw"
        ).limit(1).execute()

        if earliest.data:
            first_year = earliest.data[0]["impact_date_raw"]
            updates.append({
                "city_id": city_id,
                "polity_id": polity_id,
                "first_individual_year": first_year
            })

    print(f"\nUpdating {len(updates)} records with first_individual_year...")

    # Update in batches
    batch_size = 100
    for i in tqdm(range(0, len(updates), batch_size)):
        batch = updates[i:i + batch_size]
        for update in batch:
            db.table("top_cities_cache").update({
                "first_individual_year": update["first_individual_year"]
            }).eq("city_id", update["city_id"]).eq(
                "polity_id", update["polity_id"]
            ).execute()

    print("Done!")


if __name__ == "__main__":
    main()
