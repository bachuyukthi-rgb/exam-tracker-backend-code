# middleware/auth.py
# FastAPI dependency that verifies the Supabase JWT from the Authorization header.
# Use as: current_user: dict = Depends(get_current_user)

import os
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError, ExpiredSignatureError
from dotenv import load_dotenv

load_dotenv()

JWT_SECRET: str = os.getenv("SUPABASE_JWT_SECRET", "")

if not JWT_SECRET:
    raise EnvironmentError("Missing SUPABASE_JWT_SECRET in .env file.")

# HTTPBearer extracts the token from "Authorization: Bearer <token>"
bearer_scheme = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> dict:
    """
    Verifies the Supabase JWT and returns the decoded user payload.
    Raises HTTP 401 if the token is missing, expired, or invalid.
    """
    token = credentials.credentials

    try:
        payload = jwt.decode(
            token,
            JWT_SECRET,
            algorithms=["HS256"],
            options={"verify_aud": False},  # Supabase doesn't always set 'aud'
        )
        user_id: str = payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: missing user ID.",
            )
        return {
            "id":    user_id,
            "email": payload.get("email", ""),
            "role":  payload.get("role", "authenticated"),
        }

    except ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired. Please sign in again.",
        )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token.",
        )
