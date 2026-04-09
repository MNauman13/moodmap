import os
import urllib.request
import json
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from dotenv import load_dotenv

load_dotenv()

router = APIRouter(prefix="/api/v1/user", tags=["User"])

security = HTTPBearer()
SUPABASE_URL = os.getenv("SUPABASE_URL")

# We cache the public keys so we don't have to download them on every single request
JWKS = None

def get_supabase_jwks():
    global JWKS
    if JWKS is None:
        try:
            # Fetch the public keys directly from your Supabase project
            jwks_url = f"{SUPABASE_URL}/auth/v1/.well-known/jwks.json"
            response = urllib.request.urlopen(jwks_url)
            JWKS = json.loads(response.read())
        except Exception as e:
            print(f"Failed to fetch JWKS: {e}")
            raise HTTPException(status_code=500, detail="Auth configuration error")
    return JWKS

# --- The JWT "Middleware" / Dependency ---
def get_current_user_id(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    """
    Takes the JWT token from the frontend, downloads the Supabase public keys,
    verifies the ES256 asymmetric signature, and extracts the user's UUID.
    """
    token = credentials.credentials
    try:
        # 1. Get the public keys
        jwks = get_supabase_jwks()
        
        # 2. Decode using the modern ES256 algorithm
        payload = jwt.decode(
            token, 
            jwks, 
            algorithms=["ES256"], 
            options={"verify_aud": False}
        )
        
        user_id = payload.get("sub")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
            )
        return user_id
    
    except JWTError as e:
        print(f"JWT Verification Error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Auth Failed: {str(e)}",
        )

# --- The Protected Endpoint ---
@router.get("/profile")
async def get_profile(user_id: str = Depends(get_current_user_id)):
    """
    This endpoint is protected. It will only run if the ES256 token is valid.
    """
    return {
        "message": "Authentication successful!",
        "user_id": user_id,
        "status": "You have successfully verified an asymmetric Supabase token."
    }