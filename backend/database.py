"""Database connection for the visualizer using Supabase."""

import os
from functools import lru_cache
from dotenv import load_dotenv
from supabase import create_client, Client

# Load environment variables
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_Project_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")


@lru_cache(maxsize=1)
def get_supabase_client() -> Client:
    """Get a cached Supabase client."""
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise ValueError("Missing SUPABASE_Project_URL or SUPABASE_SERVICE_KEY in .env")
    return create_client(SUPABASE_URL, SUPABASE_KEY)


def get_db() -> Client:
    """Get database client (Supabase)."""
    return get_supabase_client()
