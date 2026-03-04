"""Add trigram index for fast name search."""

import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

DB_PASSWORD = os.getenv("SUPABASE_DB_PASSWORD")
PROJECT_REF = "ucfmffrrhbwxrfcfkxkg"


def get_connection():
    """Connect to Supabase PostgreSQL."""
    # Try direct connection
    conn_str = f"postgresql://postgres:{DB_PASSWORD}@db.{PROJECT_REF}.supabase.co:5432/postgres"
    try:
        conn = psycopg2.connect(conn_str, connect_timeout=30)
        print("Connected to Supabase PostgreSQL")
        return conn
    except Exception as e:
        print(f"Direct connection failed: {e}")

    # Try pooler
    conn_str = f"postgresql://postgres.{PROJECT_REF}:{DB_PASSWORD}@aws-0-eu-central-1.pooler.supabase.com:6543/postgres"
    try:
        conn = psycopg2.connect(conn_str, connect_timeout=30)
        print("Connected via pooler")
        return conn
    except Exception as e:
        print(f"Pooler connection failed: {e}")
        raise


def add_trigram_index():
    print("Adding trigram index for fast name search...")

    conn = get_connection()
    conn.autocommit = True
    cursor = conn.cursor()

    # Enable pg_trgm extension
    print("1. Enabling pg_trgm extension...")
    cursor.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")
    print("   Done!")

    # Create GIN index for fast text search
    print("2. Creating GIN trigram index on name_en (this may take a moment)...")
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_individuals_light_name_trgm
        ON individuals_light USING gin (name_en gin_trgm_ops);
    """)
    print("   Done!")

    # Verify index exists
    cursor.execute("""
        SELECT indexname FROM pg_indexes
        WHERE tablename = 'individuals_light' AND indexname LIKE '%trgm%';
    """)
    indexes = cursor.fetchall()
    print(f"\nTrigram indexes: {[i[0] for i in indexes]}")

    cursor.close()
    conn.close()
    print("\nIndex created successfully! Name search should now be much faster.")


if __name__ == "__main__":
    add_trigram_index()
