"""Supabase data layer — thin CRUD wrappers, no business logic.

Every public method carries the user's JWT so Postgres RLS fires.
Do NOT use the service key for user-scoped reads/writes (see ADR-001).

Usage:
    db = DB(user_jwt=user_id_from_auth_dep)  # user_jwt is the raw Bearer token
    bottles = db.list_bottles()
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

from supabase import Client, create_client


def _make_client(user_jwt: str) -> Client:
    """Create a supabase client with the user JWT injected.

    A new client per request is intentional: supabase-py's postgrest
    auth state is not thread-safe to mutate on a shared instance.
    """
    url = os.environ["SUPABASE_PROJECT_URL"]
    anon_key = os.environ["SUPABASE_ANON_KEY"]
    client = create_client(url, anon_key)
    client.postgrest.auth(user_jwt)
    return client


class DB:
    def __init__(self, user_jwt: str) -> None:
        self._sb = _make_client(user_jwt)

    # ------------------------------------------------------------------
    # Bottles (inventory)
    # ------------------------------------------------------------------

    def list_bottles(self, include_inactive: bool = False, limit: int = 20, offset: int = 0) -> list[dict]:
        q = self._sb.table("bottles").select("*").order("name")
        if not include_inactive:
            q = q.eq("is_active", True)
        return q.range(offset, offset + limit - 1).execute().data

    def get_bottle(self, bottle_id: str) -> dict | None:
        rows = self._sb.table("bottles").select("*").eq("id", bottle_id).execute().data
        return rows[0] if rows else None

    def create_bottle(self, name: str, category: str, subcategory: str | None) -> dict:
        return self._sb.table("bottles").insert(
            {"name": name, "category": category, "subcategory": subcategory}
        ).execute().data[0]

    def update_bottle(self, bottle_id: str, **fields: Any) -> dict | None:
        rows = self._sb.table("bottles").update(fields).eq("id", bottle_id).execute().data
        return rows[0] if rows else None

    def delete_bottle(self, bottle_id: str) -> bool:
        rows = self._sb.table("bottles").update({"is_active": False}).eq("id", bottle_id).execute().data
        return bool(rows)

    # ------------------------------------------------------------------
    # Companions
    # ------------------------------------------------------------------

    def list_companions(self, limit: int = 20, offset: int = 0) -> list[dict]:
        return (
            self._sb.table("companions").select("*").order("name")
            .range(offset, offset + limit - 1).execute().data
        )

    def get_companion(self, companion_id: str) -> dict | None:
        rows = self._sb.table("companions").select("*").eq("id", companion_id).execute().data
        return rows[0] if rows else None

    def create_companion(self, name: str) -> dict:
        return self._sb.table("companions").insert({"name": name}).execute().data[0]

    def update_companion(self, companion_id: str, name: str) -> dict | None:
        rows = self._sb.table("companions").update({"name": name}).eq("id", companion_id).execute().data
        return rows[0] if rows else None

    def delete_companion(self, companion_id: str) -> bool:
        rows = self._sb.table("companions").delete().eq("id", companion_id).execute().data
        return bool(rows)

    # ------------------------------------------------------------------
    # Companion preferences
    # ------------------------------------------------------------------

    def list_preferences(self, companion_id: str) -> list[dict]:
        return (
            self._sb.table("companion_preferences").select("*")
            .eq("companion_id", companion_id).order("value").execute().data
        )

    def create_preference(self, companion_id: str, pref_type: str, value: str) -> dict:
        return self._sb.table("companion_preferences").insert(
            {"companion_id": companion_id, "type": pref_type, "value": value}
        ).execute().data[0]

    def delete_preference(self, preference_id: str) -> bool:
        rows = self._sb.table("companion_preferences").delete().eq("id", preference_id).execute().data
        return bool(rows)

    def upsert_companion_like(self, companion_id: str, value: str) -> None:
        self._sb.rpc("upsert_companion_like", {"p_companion_id": companion_id, "p_value": value}).execute()

    def upsert_companion_dislike(self, companion_id: str, value: str) -> None:
        self._sb.rpc("upsert_companion_dislike", {"p_companion_id": companion_id, "p_value": value}).execute()

    # ------------------------------------------------------------------
    # Sessions
    # ------------------------------------------------------------------

    def list_sessions(self, limit: int = 20, offset: int = 0) -> list[dict]:
        return (
            self._sb.table("sessions").select("*, session_companions(companion_id)")
            .order("created_at", desc=True).range(offset, offset + limit - 1).execute().data
        )

    def get_session(self, session_id: str) -> dict | None:
        rows = (
            self._sb.table("sessions").select("*, session_companions(companion_id)")
            .eq("id", session_id).execute().data
        )
        return rows[0] if rows else None

    def get_active_session(self) -> dict | None:
        rows = (
            self._sb.table("sessions").select("*, session_companions(companion_id)")
            .is_("ended_at", "null").execute().data
        )
        return rows[0] if rows else None

    def create_session(self, occasion: str, mood: str | None, companion_ids: list[str]) -> dict:
        session = self._sb.table("sessions").insert(
            {"occasion": occasion, "mood": mood}
        ).execute().data[0]
        if companion_ids:
            self._sb.table("session_companions").insert([
                {"session_id": session["id"], "companion_id": cid}
                for cid in companion_ids
            ]).execute()
        session["session_companions"] = [{"companion_id": cid} for cid in companion_ids]
        return session

    def end_session(self, session_id: str) -> dict | None:
        now = datetime.now(timezone.utc).isoformat()
        rows = (
            self._sb.table("sessions")
            .update({"ended_at": now}).eq("id", session_id).execute().data
        )
        return rows[0] if rows else None

    # ------------------------------------------------------------------
    # Session drinks
    # ------------------------------------------------------------------

    def list_session_drinks(self, session_id: str) -> list[dict]:
        return (
            self._sb.table("session_drinks").select("*")
            .eq("session_id", session_id).order("created_at").execute().data
        )

    def get_session_drink(self, drink_id: str) -> dict | None:
        rows = self._sb.table("session_drinks").select("*").eq("id", drink_id).execute().data
        return rows[0] if rows else None

    def create_session_drinks(self, session_id: str, drinks: list[dict]) -> list[dict]:
        rows = [{"session_id": session_id, **d} for d in drinks]
        return self._sb.table("session_drinks").insert(rows).execute().data

    def set_verdict(self, drink_id: str, verdict: str) -> dict | None:
        rows = (
            self._sb.table("session_drinks")
            .update({"verdict": verdict}).eq("id", drink_id).execute().data
        )
        return rows[0] if rows else None

    # ------------------------------------------------------------------
    # Companion history
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Telemetry
    # ------------------------------------------------------------------

    def update_session_telemetry(
        self,
        session_id: str,
        bottle_count: int,
        input_tokens: int,
        output_tokens: int,
        latency_ms: int,
    ) -> None:
        """Accumulate tokens; overwrite bottle_count and latency_ms with latest call."""
        existing = self.get_session(session_id)
        if existing is None:
            return
        prev_in = existing.get("input_tokens") or 0
        prev_out = existing.get("output_tokens") or 0
        self._sb.table("sessions").update(
            {
                "bottle_count": bottle_count,
                "input_tokens": prev_in + input_tokens,
                "output_tokens": prev_out + output_tokens,
                "latency_ms": latency_ms,
            }
        ).eq("id", session_id).execute()

    def get_session_stats(self) -> dict:
        """Per-user aggregate telemetry. NULL rows excluded from token/latency averages."""
        rows = self._sb.table("sessions").select(
            "id, input_tokens, output_tokens, latency_ms, bottle_count"
        ).execute().data
        total = len(rows)
        token_rows = [r for r in rows if r.get("input_tokens") is not None]
        latency_rows = [r for r in rows if r.get("latency_ms") is not None]
        bottle_rows = [r for r in rows if r.get("bottle_count") is not None]
        return {
            "total_sessions": total,
            "total_input_tokens": sum(r["input_tokens"] for r in token_rows),
            "total_output_tokens": sum(r["output_tokens"] for r in token_rows),
            "avg_latency_ms": (
                round(sum(r["latency_ms"] for r in latency_rows) / len(latency_rows))
                if latency_rows else None
            ),
            "avg_bottle_count": (
                round(sum(r["bottle_count"] for r in bottle_rows) / len(bottle_rows))
                if bottle_rows else None
            ),
        }

    # ------------------------------------------------------------------
    # Companion history
    # ------------------------------------------------------------------

    def get_companion_history(self, companion_id: str) -> list[dict]:
        """All drinks from sessions where this companion was present."""
        sc_rows = (
            self._sb.table("session_companions")
            .select("session_id")
            .eq("companion_id", companion_id)
            .execute().data
        )
        session_ids = [r["session_id"] for r in sc_rows]
        if not session_ids:
            return []
        return (
            self._sb.table("session_drinks")
            .select("id, session_id, name, verdict, created_at")
            .in_("session_id", session_ids)
            .order("created_at")
            .execute().data
        )
