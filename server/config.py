"""Website settings, read from the environment (or .env)."""

import os

from dotenv import load_dotenv

load_dotenv()

# Supabase project (Project Settings -> API Keys). The publishable key is
# safe to send to browsers; the secret key must stay on the server.
SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SUPABASE_PUBLISHABLE_KEY = os.getenv("SUPABASE_PUBLISHABLE_KEY", "")
SUPABASE_SECRET_KEY = os.getenv("SUPABASE_SECRET_KEY", "")

# Comma-separated emails that can open the admin page.
ADMIN_EMAILS = {email.strip().lower() for email in os.getenv("ADMIN_EMAILS", "").split(",") if email.strip()}

# Free-tier guards: Groq's 120B model allows roughly 8-10 full plans a day
# across everyone, so keep per-person and site-wide caps below that.
PLANS_PER_USER_PER_DAY = int(os.getenv("PLANS_PER_USER_PER_DAY", "3"))
PLANS_PER_DAY_TOTAL = int(os.getenv("PLANS_PER_DAY_TOTAL", "8"))
MESSAGES_PER_USER_PER_DAY = int(os.getenv("MESSAGES_PER_USER_PER_DAY", "20"))

MAX_MESSAGE_CHARS = 2000


def missing_settings() -> list:
    names = {
        "SUPABASE_URL": SUPABASE_URL,
        "SUPABASE_PUBLISHABLE_KEY": SUPABASE_PUBLISHABLE_KEY,
        "SUPABASE_SECRET_KEY": SUPABASE_SECRET_KEY,
    }
    return [name for name, value in names.items() if not value]
