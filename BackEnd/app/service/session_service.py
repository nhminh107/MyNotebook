"""Signed, expiring HTTP-only sessions for document and citation access."""

from datetime import datetime, timedelta, timezone
from functools import lru_cache
import logging
import os
import secrets

from fastapi import HTTPException, Request, Response
from jose import JWTError, jwt

SESSION_COOKIE = "notebook_session"
SESSION_SECONDS = 86_400
logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def session_secret() -> str:
    """Use a configured shared secret, or an ephemeral single-process secret."""
    configured = os.environ.get("NOTEBOOK_SESSION_SECRET")
    if configured:
        if len(configured) < 32:
            raise RuntimeError("NOTEBOOK_SESSION_SECRET must contain at least 32 characters.")
        return configured
    logger.warning("Using an ephemeral session secret; restarts require login. Configure NOTEBOOK_SESSION_SECRET for multiple workers.")
    return secrets.token_urlsafe(48)


def set_session(response: Response, user_id: str, secure: bool = False) -> None:
    """Issue a signed cookie without adding credentials to API response bodies."""
    now = datetime.now(timezone.utc)
    token = jwt.encode({
        "sub": user_id, "iat": now, "exp": now + timedelta(seconds=SESSION_SECONDS),
        "aud": "notebook", "iss": "notebook",
    }, session_secret(), algorithm="HS256")
    response.set_cookie(
        SESSION_COOKIE, token, max_age=SESSION_SECONDS, httponly=True,
        secure=secure, samesite="strict", path="/",
    )


async def require_document_identity(request: Request) -> str:
    """Authenticate and bind supplied user identifiers to the signed identity."""
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise HTTPException(status_code=401, detail="Please sign in to access documents.")
    try:
        claims = jwt.decode(token, session_secret(), algorithms=["HS256"],
                            audience="notebook", issuer="notebook")
        user_id = claims["sub"]
        if not isinstance(user_id, str) or not user_id:
            raise ValueError("Missing session identity")
    except (JWTError, ValueError, KeyError) as exc:
        raise HTTPException(status_code=401, detail="Session expired. Please sign in again.") from exc
    supplied = request.path_params.get("user_id")
    if request.method == "POST":
        content_type = request.headers.get("content-type", "")
        if content_type.startswith("application/json"):
            payload = await request.json()
            supplied = payload.get("user_id") if isinstance(payload, dict) else None
        elif content_type.startswith("multipart/form-data"):
            supplied = (await request.form()).get("user_id")
    if supplied is not None and str(supplied).strip() != user_id:
        raise HTTPException(status_code=403, detail="You cannot access another user's documents.")
    request.state.user_id = user_id
    return user_id
