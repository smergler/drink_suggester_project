"""FastAPI auth dependency — verifies Supabase JWTs locally.

Supabase issues HS256 JWTs signed with the project JWT secret.
We verify offline (no network call) so auth adds ~0ms per request.

Usage:
    @app.get("/me")
    def me(user_id: str = Depends(get_current_user)):
        ...
"""

from __future__ import annotations

import os

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

bearer_scheme = HTTPBearer()
_bearer = bearer_scheme  # internal alias used by get_current_user


def get_current_user(
    creds: HTTPAuthorizationCredentials = Depends(_bearer),
) -> str:
    """Verify the Bearer JWT and return the Supabase user_id (sub claim).

    Raises HTTP 401 on any verification failure.
    Raises HTTP 503 if SUPABASE_JWT_TOKEN is not configured.

    We check both aud="authenticated" AND role="authenticated" to guard
    against Supabase's anon/service_role keys (same secret, different role).
    """
    secret = os.environ.get("SUPABASE_JWT_TOKEN")
    if not secret:
        raise HTTPException(status_code=503, detail="Auth not configured (SUPABASE_JWT_TOKEN missing)")

    try:
        payload = jwt.decode(
            creds.credentials,
            secret,
            algorithms=["HS256"],
            audience="authenticated",
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {e}")

    # Guard against service_role / anon tokens: they share the same secret
    # but have role != "authenticated".
    if payload.get("role") != "authenticated":
        raise HTTPException(status_code=401, detail="Token role not permitted")

    user_id: str | None = payload.get("sub")
    if user_id is None:
        raise HTTPException(status_code=401, detail="Token missing sub claim")
    return user_id
