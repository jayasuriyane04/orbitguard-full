import os
import secrets
from fastapi import Header, HTTPException, status
from slowapi import Limiter
from slowapi.util import get_remote_address

# API keys are read from environment, never hardcoded. In production these
# would be issued per-client and stored hashed in a database, not as a flat
# env var -- this is a minimal viable version for a small internal service.
_RAW_KEYS = os.environ.get("DEBRIS_TRACKER_API_KEYS", "")
VALID_API_KEYS = {k.strip() for k in _RAW_KEYS.split(",") if k.strip()}

if not VALID_API_KEYS:
    # Dev fallback so the service is runnable out of the box; logs a loud
    # warning rather than silently accepting unauthenticated requests.
    _dev_key = secrets.token_urlsafe(24)
    VALID_API_KEYS = {_dev_key}
    print(f"[security] DEBRIS_TRACKER_API_KEYS not set -- generated dev key: {_dev_key}")


def require_api_key(x_api_key: str | None = Header(default=None)) -> str:
    if not x_api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing X-API-Key header")
    # constant-time comparison against each valid key to avoid timing leaks
    if not any(secrets.compare_digest(x_api_key, k) for k in VALID_API_KEYS):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid API key")
    return x_api_key


limiter = Limiter(key_func=get_remote_address, default_limits=["120/minute"])
