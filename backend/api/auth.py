"""Authentication endpoints — register, login, refresh, me, logout."""

import logging
import time
from collections import defaultdict

import fastapi
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.dependencies import get_current_user
from backend.api.models import AuthResponse, LoginRequest, RegisterRequest, TokenResponse, UserResponse
from backend.config import settings
from backend.db.engine import get_db
from backend.db.models import User
from backend.utils.auth import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    validate_password,
    verify_password,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])

# In-memory rate limiting
_login_attempts: dict[str, list[float]] = defaultdict(list)
_RATE_LIMIT_WINDOW = 15 * 60  # 15 minutes
_RATE_LIMIT_MAX = 5
_RATE_LIMIT_CLEANUP_THRESHOLD = 1000

# Register rate limiting (per IP)
_register_attempts: dict[str, list[float]] = defaultdict(list)
_REGISTER_RATE_LIMIT_WINDOW = 60 * 60  # 1 hour
_REGISTER_RATE_LIMIT_MAX = 3


def _check_rate_limit(email: str) -> None:
    now = time.time()
    # Prune all expired entries when dict gets large (S4: prevent memory leak)
    if len(_login_attempts) > _RATE_LIMIT_CLEANUP_THRESHOLD:
        expired_keys = [
            k for k, v in _login_attempts.items()
            if not any(now - t < _RATE_LIMIT_WINDOW for t in v)
        ]
        for k in expired_keys:
            del _login_attempts[k]
    attempts = _login_attempts[email]
    _login_attempts[email] = [t for t in attempts if now - t < _RATE_LIMIT_WINDOW]
    if len(_login_attempts[email]) >= _RATE_LIMIT_MAX:
        raise HTTPException(status_code=429, detail="Too many login attempts. Try again later.")


def _check_register_rate_limit(ip: str) -> None:
    """Limit registration attempts per IP address (3/hour)."""
    now = time.time()
    attempts = _register_attempts[ip]
    _register_attempts[ip] = [t for t in attempts if now - t < _REGISTER_RATE_LIMIT_WINDOW]
    if len(_register_attempts[ip]) >= _REGISTER_RATE_LIMIT_MAX:
        raise HTTPException(status_code=429, detail="Too many registration attempts. Try again later.")


@router.post("/register", response_model=AuthResponse)
async def register(
    req: RegisterRequest,
    request: fastapi.Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> AuthResponse:
    client_ip = request.client.host if request.client else "unknown"
    _check_register_rate_limit(client_ip)
    _register_attempts[client_ip].append(time.time())

    errors = validate_password(req.password)
    if errors:
        raise HTTPException(status_code=422, detail=errors)

    existing = await db.execute(select(User).where(User.email == req.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Email already registered")

    user = User(email=req.email, password_hash=hash_password(req.password), name=req.name)
    db.add(user)
    await db.commit()
    await db.refresh(user)

    access_token = create_access_token(
        user_id=str(user.id), secret=settings.JWT_SECRET,
        expiry_minutes=settings.JWT_ACCESS_TOKEN_EXPIRY_MINUTES,
    )
    refresh_token = create_refresh_token(
        user_id=str(user.id), secret=settings.JWT_SECRET,
        expiry_days=settings.JWT_REFRESH_TOKEN_EXPIRY_DAYS,
    )

    response.set_cookie(
        key="refresh_token", value=refresh_token,
        httponly=True, secure=True, samesite="lax",
        max_age=settings.JWT_REFRESH_TOKEN_EXPIRY_DAYS * 86400,
    )

    logger.info("User registered: %s", user.email)
    return AuthResponse(
        user={"id": str(user.id), "email": user.email, "name": user.name},
        access_token=access_token,
    )


@router.post("/login", response_model=AuthResponse)
async def login(
    req: LoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> AuthResponse:
    email = req.email.lower().strip()
    _check_rate_limit(email)

    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if not user or not verify_password(req.password, user.password_hash):
        _login_attempts[email].append(time.time())
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is deactivated")

    access_token = create_access_token(
        user_id=str(user.id), secret=settings.JWT_SECRET,
        expiry_minutes=settings.JWT_ACCESS_TOKEN_EXPIRY_MINUTES,
    )
    refresh_token = create_refresh_token(
        user_id=str(user.id), secret=settings.JWT_SECRET,
        expiry_days=settings.JWT_REFRESH_TOKEN_EXPIRY_DAYS,
    )

    response.set_cookie(
        key="refresh_token", value=refresh_token,
        httponly=True, secure=True, samesite="lax",
        max_age=settings.JWT_REFRESH_TOKEN_EXPIRY_DAYS * 86400,
    )

    return AuthResponse(
        user={"id": str(user.id), "email": user.email, "name": user.name},
        access_token=access_token,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    request: fastapi.Request,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    token = request.cookies.get("refresh_token")
    if not token:
        raise HTTPException(status_code=401, detail="No refresh token")

    import jwt as pyjwt
    try:
        payload = decode_token(token, settings.JWT_SECRET)
    except (pyjwt.ExpiredSignatureError, pyjwt.InvalidTokenError):
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid token type")

    result = await db.execute(select(User).where(User.id == payload["sub"]))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or deactivated")

    access_token = create_access_token(
        user_id=str(user.id), secret=settings.JWT_SECRET,
        expiry_minutes=settings.JWT_ACCESS_TOKEN_EXPIRY_MINUTES,
    )
    return TokenResponse(access_token=access_token)


@router.get("/me", response_model=UserResponse)
async def me(
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return UserResponse(
        id=str(user.id), email=user.email, name=user.name,
        created_at=user.created_at.isoformat(),
    )


@router.post("/logout")
async def logout(response: Response) -> dict:
    response.delete_cookie("refresh_token")
    return {"message": "Logged out"}
