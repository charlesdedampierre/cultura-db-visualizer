"""Add index on birthcity_id to speed up city search queries."""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.database import get_db

def main():
    db = get_db()
    
    print("Creating index on individuals_light(birthcity_id, polity_id, impact_date_raw)...")
    
    # Create composite index for the query we need
    # This will speed up: WHERE polity_id = X AND birthcity_id = Y ORDER BY impact_date_raw
    try:
        db.postgrest.session.execute("""
            CREATE INDEX IF NOT EXISTS idx_il_birthcity_polity_impact 
            ON individuals_light(birthcity_id, polity_id, impact_date_raw);
        """)
        print("Index created successfully!")
    except Exception as e:
        print(f"Error creating index: {e}")
        print("You may need to run this SQL manually in Supabase:")
        print("CREATE INDEX IF NOT EXISTS idx_il_birthcity_polity_impact ON individuals_light(birthcity_id, polity_id, impact_date_raw);")

if __name__ == "__main__":
    main()
