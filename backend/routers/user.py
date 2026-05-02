import os
import time
import json
import logging
from dataclasses import dataclass
import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/user", tags=["User"])

security = HTTPBearer()
SUPABASE_URL = os.getenv("SUPABASE_URL")

_jwks_cache: dict | None = None
_jwks_cache_until: float = 0.0
# 1h TTL so a Supabase key rotation propagates within an hour.
# Going to 24h means a rotation effectively locks every authenticated
# request out for up to a day — verified outage scenario, not theoretical.
_JWKS_TTL = 3_600


@dataclass(frozen=True)
class AuthenticatedUser:
    user_id: str
    email: str | None = None


def get_supabase_jwks():
    global _jwks_cache, _jwks_cache_until
    if _jwks_cache is None or time.time() > _jwks_cache_until:
        try:
            jwks_url = f"{SUPABASE_URL}/auth/v1/.well-known/jwks.json"
            # httpx.get() is a sync call; FastAPI runs sync dependencies in the
            # default thread-pool executor so this does NOT block the event loop.
            with httpx.Client(timeout=5.0) as client:
                response = client.get(jwks_url)
                response.raise_for_status()
                _jwks_cache = response.json()
            _jwks_cache_until = time.time() + _JWKS_TTL
        except Exception as e:
            logger.error(f"Failed to fetch JWKS: {e}")
            if _jwks_cache is not None:
                logger.warning("Using stale JWKS cache due to fetch failure")
                return _jwks_cache
            raise HTTPException(status_code=500, detail="Auth configuration error")
    return _jwks_cache


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> AuthenticatedUser:
    token = credentials.credentials
    try:
        jwks = get_supabase_jwks()
        # Supabase issues every user JWT with aud="authenticated". Verifying
        # the audience prevents service-role tokens or tokens minted for a
        # different audience from being accepted by user-facing endpoints.
        payload = jwt.decode(
            token,
            jwks,
            algorithms=["ES256"],
            audience="authenticated",
        )
        user_id = payload.get("sub")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
            )
        return AuthenticatedUser(
            user_id=user_id,
            email=payload.get("email"),
        )
    except JWTError as e:
        # Log the real reason internally; never echo it back — JWT error
        # text can disclose key IDs, claim names, or rotation state.
        logger.warning("JWT verification failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
        )


def get_current_user_id(
    current_user: AuthenticatedUser = Depends(get_current_user)
) -> str:
    return current_user.user_id

# --- The Protected Endpoint ---
@router.get("/profile")
async def get_profile(current_user: AuthenticatedUser = Depends(get_current_user)):
    """
    This endpoint is protected. It will only run if the ES256 token is valid.
    """
    return {
        "message": "Authentication successful!",
        "user_id": current_user.user_id,
        "email": current_user.email,
        "status": "You have successfully verified an asymmetric Supabase token."
    }
