# routes/auth.py
# Auth endpoints: signup, login, logout, /me, reset-password, refresh

import os
from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel, EmailStr
from typing import Optional
from config.supabase import supabase
from middleware.auth import get_current_user
from dotenv import load_dotenv

load_dotenv()

router = APIRouter(prefix="/api/auth", tags=["Auth"])

FRONTEND_URL = os.getenv("FRONTEND_URL", "http://127.0.0.1:5500")


# ── SCHEMAS ──────────────────────────────────────────────────
class SignupRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: Optional[str] = ""

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class ResetPasswordRequest(BaseModel):
    email: EmailStr

class RefreshRequest(BaseModel):
    refresh_token: str


# ── POST /api/auth/signup ─────────────────────────────────────
@router.post("/signup", status_code=status.HTTP_201_CREATED)
async def signup(body: SignupRequest):
    if len(body.password) < 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 6 characters.",
        )
    try:
        result = supabase.auth.admin.create_user({
            "email":          body.email,
            "password":       body.password,
            "user_metadata":  {"full_name": body.full_name or ""},
            "email_confirm":  False,  # set True to require email verification
        })
        user = result.user
        return {
            "success": True,
            "message": "Account created successfully.",
            "user": {
                "id":    user.id,
                "email": user.email,
                "name":  user.user_metadata.get("full_name", "") if user.user_metadata else "",
            },
        }
    except Exception as e:
        msg = str(e)
        if "already registered" in msg.lower():
            raise HTTPException(status_code=400, detail="This email is already registered.")
        raise HTTPException(status_code=400, detail=msg)


# ── POST /api/auth/login ──────────────────────────────────────
@router.post("/login")
async def login(body: LoginRequest):
    try:
        result = supabase.auth.sign_in_with_password({
            "email":    body.email,
            "password": body.password,
        })
        session = result.session
        user    = result.user

        if not session:
            raise HTTPException(status_code=401, detail="Invalid email or password.")

        return {
            "success":       True,
            "message":       "Login successful.",
            "access_token":  session.access_token,
            "refresh_token": session.refresh_token,
            "expires_at":    session.expires_at,
            "user": {
                "id":    user.id,
                "email": user.email,
                "name":  user.user_metadata.get("full_name", "") if user.user_metadata else "",
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        msg = str(e)
        if "invalid" in msg.lower() or "credentials" in msg.lower():
            raise HTTPException(status_code=401, detail="Invalid email or password.")
        raise HTTPException(status_code=400, detail=msg)


# ── POST /api/auth/logout ─────────────────────────────────────
@router.post("/logout")
async def logout(current_user: dict = Depends(get_current_user)):
    try:
        supabase.auth.admin.sign_out(current_user["id"])
        return {"success": True, "message": "Logged out successfully."}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── GET /api/auth/me ──────────────────────────────────────────
@router.get("/me")
async def get_me(current_user: dict = Depends(get_current_user)):
    try:
        result = supabase.auth.admin.get_user_by_id(current_user["id"])
        user   = result.user
        if not user:
            raise HTTPException(status_code=404, detail="User not found.")
        return {
            "success": True,
            "user": {
                "id":           user.id,
                "email":        user.email,
                "name":         user.user_metadata.get("full_name", "") if user.user_metadata else "",
                "created_at":   str(user.created_at),
                "last_sign_in": str(user.last_sign_in_at),
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── POST /api/auth/reset-password ────────────────────────────
@router.post("/reset-password")
async def reset_password(body: ResetPasswordRequest):
    try:
        supabase.auth.reset_password_email(
            body.email,
            options={"redirect_to": f"{FRONTEND_URL}/reset"},
        )
        # Always return success to prevent email enumeration
        return {
            "success": True,
            "message": "If that email exists, a reset link has been sent.",
        }
    except Exception:
        return {
            "success": True,
            "message": "If that email exists, a reset link has been sent.",
        }


# ── POST /api/auth/refresh ────────────────────────────────────
@router.post("/refresh")
async def refresh_token(body: RefreshRequest):
    try:
        result  = supabase.auth.refresh_session(body.refresh_token)
        session = result.session
        if not session:
            raise HTTPException(status_code=401, detail="Invalid or expired refresh token.")
        return {
            "success":       True,
            "access_token":  session.access_token,
            "refresh_token": session.refresh_token,
            "expires_at":    session.expires_at,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))
