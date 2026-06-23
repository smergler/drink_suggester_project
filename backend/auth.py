"""FastAPI auth dependency — verifies Supabase JWTs locally.

New Supabase projects (publishable-key format) sign with RS256; tokens are
verified against the project's JWKS endpoint (one cached network fetch).
Legacy projects and test-issued tokens use HS256 with SUPABASE_JWT_TOKEN.

Algorithm routing is based on the token's own `alg` header — each path uses
a fixed, independent key so there is no algorithm-confusion risk.
"""

from __future__ import annotations

import os

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

bearer_scheme = HTTPBearer()
_bearer = bearer_scheme  # internal alias used by get_current_user

_jwks_client: jwt.PyJWKClient | None = None


def _get_jwks_client() -> jwt.PyJWKClient:
    global _jwks_client
    if _jwks_client is None:
        url = os.environ["SUPABASE_PROJECT_URL"]
        jwks_uri = f"{url.rstrip('/')}/auth/v1/.well-known/jwks.json"
        _jwks_client = jwt.PyJWKClient(jwks_uri, cache_jwk_set=True, lifespan=3600)
    return _jwks_client


def get_current_user(
    creds: HTTPAuthorizationCredentials = Depends(_bearer),
) -> str:
    """Verify the Bearer JWT and return the Supabase user_id (sub claim).

    Routes to RS256 (JWKS) or HS256 (shared secret) based on the token header.
    Raises HTTP 401 on any verification failure, 503 if env is misconfigured.
    """
    token = creds.credentials

    try:
        header = jwt.get_unverified_header(token)
    except jwt.InvalidTokenError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {e}")

    alg = header.get("alg", "")

    try:
        if alg == "RS256":
            url = os.environ.get("SUPABASE_PROJECT_URL")
            if not url:
                raise HTTPException(
                    status_code=503,
                    detail="Auth not configured (SUPABASE_PROJECT_URL missing)",
                )
            signing_key = _get_jwks_client().get_signing_key_from_jwt(token)
            payload = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256"],
                audience="authenticated",
            )
        elif alg == "HS256":
            secret = os.environ.get("SUPABASE_JWT_TOKEN")
            if not secret:
                raise HTTPException(
                    status_code=503,
                    detail="Auth not configured (SUPABASE_JWT_TOKEN missing)",
                )
            payload = jwt.decode(
                token,
                secret,
                algorithms=["HS256"],
                audience="authenticated",
            )
        else:
            raise HTTPException(status_code=401, detail=f"Unsupported token algorithm: {alg!r}")
    except HTTPException:
        raise
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {e}")
    except jwt.exceptions.PyJWKClientError as e:
        raise HTTPException(status_code=503, detail=f"Auth service unavailable: {e}")

    if payload.get("role") != "authenticated":
        raise HTTPException(status_code=401, detail="Token role not permitted")

    user_id: str | None = payload.get("sub")
    if user_id is None:
        raise HTTPException(status_code=401, detail="Token missing sub claim")
    return user_id
