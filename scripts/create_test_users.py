"""Create two Supabase test users and write their credentials to .env.

Run once:
    .venv/bin/python scripts/create_test_users.py

Requires SUPABASE_PROJECT_URL and SUPABASE_PRIVATE_KEY in .env.
Writes TEST_USER_A_EMAIL, TEST_USER_A_PASSWORD, TEST_USER_B_EMAIL,
TEST_USER_B_PASSWORD to .env if they are not already present.
"""

from __future__ import annotations

import os
import secrets
import string
from pathlib import Path

from dotenv import load_dotenv
from supabase import create_client

ENV_PATH = Path(__file__).parent.parent / ".env"

load_dotenv(ENV_PATH)

url = os.environ.get("SUPABASE_PROJECT_URL")
service_key = os.environ.get("SUPABASE_PRIVATE_KEY")

if not url or not service_key:
    raise SystemExit("SUPABASE_PROJECT_URL and SUPABASE_PRIVATE_KEY must be set in .env")

sb = create_client(url, service_key)

# Generate secure passwords
_chars = string.ascii_letters + string.digits + "!@#$"
def _pw() -> str:
    return "".join(secrets.choice(_chars) for _ in range(20))

users = [
    ("TEST_USER_A_EMAIL", "TEST_USER_A_PASSWORD", "test-rls-a@example.com"),
    ("TEST_USER_B_EMAIL", "TEST_USER_B_PASSWORD", "test-rls-b@example.com"),
]

# Read existing .env content
env_text = ENV_PATH.read_text() if ENV_PATH.exists() else ""
existing_keys = {line.split("=", 1)[0] for line in env_text.splitlines() if "=" in line}

additions: list[str] = []
for email_key, pw_key, email in users:
    if email_key in existing_keys and pw_key in existing_keys:
        print(f"  {email_key} already in .env — skipping user creation")
        continue

    pw = _pw()
    try:
        result = sb.auth.admin.create_user({
            "email": email,
            "password": pw,
            "email_confirm": True,
        })
        print(f"  Created: {result.user.email} (id={result.user.id})")
    except Exception as e:
        if "already been registered" in str(e) or "already exists" in str(e).lower():
            # User exists; generate new password and update it
            print(f"  {email} already exists — resetting password")
            # Find user and update
            users_list = sb.auth.admin.list_users()
            existing = next((u for u in users_list if u.email == email), None)
            if existing:
                sb.auth.admin.update_user_by_id(str(existing.id), {"password": pw})
            else:
                raise
        else:
            raise

    additions.append(f"{email_key}={email}")
    additions.append(f"{pw_key}={pw}")

if additions:
    sep = "\n" if env_text.endswith("\n") else "\n\n"
    with open(ENV_PATH, "a") as f:
        f.write(sep + "\n".join(additions) + "\n")
    print(f"\nWrote {len(additions)} vars to {ENV_PATH}")
else:
    print("\nNo changes — all test user vars already present in .env")

print("Done. Run: .venv/bin/python -m pytest tests/test_rls_isolation.py -v")
