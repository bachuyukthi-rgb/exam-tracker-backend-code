# config/supabase.py
# Supabase admin client using the Service Role key.
# This bypasses Row Level Security — safe for backend use only.

import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY: str = os.getenv("SUPABASE_SERVICE_KEY", "")

if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
    raise EnvironmentError(
        "Missing SUPABASE_URL or SUPABASE_SERVICE_KEY in .env file.\n"
        "Find them at: Supabase Dashboard → Settings → API"
    )

# Admin client — full DB access, bypasses RLS
supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
