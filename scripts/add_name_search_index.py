"""
Add trigram index for fast name search in Supabase.

This enables fast ILIKE/similarity queries on the name_en column.
Run this once after creating the tables.

Usage:
    python scripts/add_name_search_index.py

Or copy the SQL below and run in Supabase Dashboard > SQL Editor:

    CREATE EXTENSION IF NOT EXISTS pg_trgm;
    CREATE INDEX IF NOT EXISTS idx_individuals_light_name_trgm
        ON individuals_light USING gin (name_en gin_trgm_ops);
"""


def main():
    print("=" * 60)
    print("Name Search Index")
    print("=" * 60)
    print()
    print("Copy and paste the following SQL into Supabase Dashboard > SQL Editor:")
    print()
    print("-" * 60)
    print("""
-- Enable trigram extension for fast text search
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Create GIN index on name_en for fast ILIKE queries
CREATE INDEX IF NOT EXISTS idx_individuals_light_name_trgm
    ON individuals_light USING gin (name_en gin_trgm_ops);

-- Optional: Create index on city name for search
CREATE INDEX IF NOT EXISTS idx_top_cities_name_trgm
    ON top_cities_cache USING gin (city_name gin_trgm_ops);
""")
    print("-" * 60)
    print()
    print("After running this, name searches will be much faster!")


if __name__ == "__main__":
    main()
