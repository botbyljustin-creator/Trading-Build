"""Clerk authentication.

Verifies the `Authorization: Bearer <session_jwt>` header issued by Clerk
against Clerk's published JWKS (`Settings.clerk_jwks_url`), never trusting
an unsigned claim. `get_current_user` additionally syncs the verified
identity into our own `users` table (create-if-missing, keep email fresh)
so every other table can foreign-key against a stable internal user id
rather than a third-party subject string.

`AUTH_DEV_MODE=true` is a local-only escape hatch (refused outside
`app_env == "development"`) that skips Clerk entirely and authenticates as
a single fixed dev user, so the pipeline can be exercised without a Clerk
account while building. It must never be enabled in a deployed environment.
"""

from __future__ import annotations

from functools import lru_cache

import jwt
from fastapi import Depends, HTTPException, Request, status
from jwt import PyJWKClient
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.db import get_db
from app.core.logging import get_logger
from app.models.user import User

logger = get_logger(__name__)

DEV_USER_CLERK_ID = "dev_local_user"
DEV_USER_EMAIL = "dev@localhost"


class AuthError(HTTPException):
    def __init__(self, detail: str) -> None:
        super().__init__(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)


@lru_cache
def _jwk_client(jwks_url: str) -> PyJWKClient:
    return PyJWKClient(jwks_url)


def _verify_clerk_jwt(token: str, settings: Settings) -> dict:
    if not settings.clerk_jwks_url:
        raise AuthError("Clerk is not configured (CLERK_JWKS_URL missing). See README.md Setup.")
    try:
        signing_key = _jwk_client(settings.clerk_jwks_url).get_signing_key_from_jwt(token)
        options = {"require": ["exp", "iat", "sub"]}
        claims: dict = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            options=options,
            issuer=settings.clerk_issuer or None,
        )
    except jwt.PyJWTError as exc:
        logger.warning("clerk_jwt_verification_failed", error=str(exc))
        raise AuthError(f"Invalid session token: {exc}") from exc
    return claims


def get_current_claims(request: Request, settings: Settings = Depends(get_settings)) -> dict:
    auth_header = request.headers.get("authorization", "")
    token = auth_header.removeprefix("Bearer ").strip() if auth_header else ""

    if not token:
        if settings.auth_dev_mode and not settings.is_production:
            return {"sub": DEV_USER_CLERK_ID, "email": DEV_USER_EMAIL}
        raise AuthError("Missing Authorization header.")

    return _verify_clerk_jwt(token, settings)


def get_current_user(
    claims: dict = Depends(get_current_claims), db: Session = Depends(get_db)
) -> User:
    clerk_user_id = claims.get("sub")
    if not clerk_user_id:
        raise AuthError("Token is missing a 'sub' claim.")
    email = claims.get("email") or f"{clerk_user_id}@unknown.clerk"

    user = db.query(User).filter(User.clerk_user_id == clerk_user_id).one_or_none()
    if user is None:
        user = User(clerk_user_id=clerk_user_id, email=email)
        db.add(user)
        db.commit()
        db.refresh(user)
        logger.info("user_created", clerk_user_id=clerk_user_id)
    elif user.email != email:
        user.email = email
        db.commit()
    return user
