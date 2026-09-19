"""Optional API key authentication.

Disabled by default (AUTH_ENABLED=false) so local development and the hackathon
demo are never blocked by auth. When enabled, every request must send a
matching `X-API-Key` header.
"""

from fastapi import Header, HTTPException, status

from app.core.config import get_settings


def verify_api_key(x_api_key: str | None = Header(default=None)) -> None:
    settings = get_settings()
    if not settings.auth_enabled:
        return
    if x_api_key is None or x_api_key != settings.api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid API key.",
        )
