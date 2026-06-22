"""Live RLS isolation tests — two real Supabase users.

These tests hit the real Supabase project to verify that Postgres Row Level
Security prevents User A from reading or writing User B's data.

Setup (human task — do once):
  1. Create two test accounts in the Supabase dashboard or via the JS client.
  2. Add to your .env:
       TEST_USER_A_EMAIL=test-a@example.com
       TEST_USER_A_PASSWORD=...
       TEST_USER_B_EMAIL=test-b@example.com
       TEST_USER_B_PASSWORD=...
  3. Run: .venv/bin/python -m pytest tests/test_rls_isolation.py -v

All tests are skipped automatically if the env vars are missing.
"""

from __future__ import annotations

import os
import pytest

_REQUIRED = [
    "TEST_USER_A_EMAIL", "TEST_USER_A_PASSWORD",
    "TEST_USER_B_EMAIL", "TEST_USER_B_PASSWORD",
    "SUPABASE_PROJECT_URL", "SUPABASE_ANON_KEY", "SUPABASE_JWT_TOKEN",
]

live_rls = pytest.mark.skipif(
    not all(os.environ.get(k) for k in _REQUIRED),
    reason="Set TEST_USER_A/B credentials in .env to run RLS isolation tests",
)


def _sign_in(email: str, password: str) -> str:
    from supabase import create_client
    client = create_client(os.environ["SUPABASE_PROJECT_URL"], os.environ["SUPABASE_ANON_KEY"])
    result = client.auth.sign_in_with_password({"email": email, "password": password})
    return result.session.access_token


@live_rls
def test_rls_read_isolation():
    """User B cannot see User A's bottles via list_bottles."""
    from backend.db import DB

    jwt_a = _sign_in(os.environ["TEST_USER_A_EMAIL"], os.environ["TEST_USER_A_PASSWORD"])
    jwt_b = _sign_in(os.environ["TEST_USER_B_EMAIL"], os.environ["TEST_USER_B_PASSWORD"])
    db_a, db_b = DB(jwt_a), DB(jwt_b)

    bottle_name = f"rls-test-read-{os.getpid()}"
    bottle = db_a.create_bottle(bottle_name, "test-spirit", None)
    bottle_id = bottle["id"]
    try:
        b_names = [b["name"] for b in db_b.list_bottles(limit=200, offset=0)]
        assert bottle_name not in b_names, (
            f"RLS FAILURE: User B can read User A's bottle '{bottle_name}'"
        )
    finally:
        db_a.delete_bottle(bottle_id)


@live_rls
def test_rls_write_isolation():
    """User B's attempt to update User A's bottle is silently blocked by RLS."""
    from backend.db import DB

    jwt_a = _sign_in(os.environ["TEST_USER_A_EMAIL"], os.environ["TEST_USER_A_PASSWORD"])
    jwt_b = _sign_in(os.environ["TEST_USER_B_EMAIL"], os.environ["TEST_USER_B_PASSWORD"])
    db_a, db_b = DB(jwt_a), DB(jwt_b)

    bottle_name = f"rls-test-write-{os.getpid()}"
    bottle = db_a.create_bottle(bottle_name, "test-spirit", None)
    bottle_id = bottle["id"]
    try:
        result = db_b.update_bottle(bottle_id, name="HACKED", category="hacked")
        assert result is None, "RLS FAILURE: User B updated User A's bottle"
        # Confirm the original name is unchanged for User A
        original = db_a.get_bottle(bottle_id)
        assert original is not None and original["name"] == bottle_name
    finally:
        db_a.delete_bottle(bottle_id)


@live_rls
def test_rls_companion_isolation():
    """User B cannot see User A's companions."""
    from backend.db import DB

    jwt_a = _sign_in(os.environ["TEST_USER_A_EMAIL"], os.environ["TEST_USER_A_PASSWORD"])
    jwt_b = _sign_in(os.environ["TEST_USER_B_EMAIL"], os.environ["TEST_USER_B_PASSWORD"])
    db_a, db_b = DB(jwt_a), DB(jwt_b)

    companion_name = f"rls-companion-{os.getpid()}"
    companion = db_a.create_companion(companion_name)
    companion_id = companion["id"]
    try:
        b_names = [c["name"] for c in db_b.list_companions(limit=200, offset=0)]
        assert companion_name not in b_names, (
            f"RLS FAILURE: User B can read User A's companion '{companion_name}'"
        )
    finally:
        db_a.delete_companion(companion_id)
