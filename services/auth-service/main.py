"""Auth Service — FastAPI microservice for authentication & user management.

Endpoints:
  POST /api/v1/auth/register   — Create a new user
  POST /api/v1/auth/login      — Login, returns JWT access + refresh tokens
  POST /api/v1/auth/refresh    — Refresh an access token
  GET  /api/v1/auth/me         — Current user profile
  PUT  /api/v1/auth/me         — Update current user profile
  GET  /api/v1/auth/users      — List users (admin only)
  GET  /health                 — Health check
"""

from __future__ import annotations

import logging
import os
import sys
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# ── Shared module imports ──
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))
from shared.utils.database import (  # noqa: E402
    close_redis,
    engine,
    get_db,
    get_redis,
)
from shared.schemas.models import (  # noqa: E402
    PaginatedResponse,
    TokenResponse,
    UserResponse,
    UserStatus,
    UserType,
)

# ── Logging ──
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("auth-service")

# ── Configuration ──
SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "super-secret-dev-key-change-me")
ALGORITHM: str = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
REFRESH_TOKEN_EXPIRE_DAYS: int = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))

# ── Password hashing ──
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# ── Security scheme ──
bearer_scheme = HTTPBearer(auto_error=False)


# ── Request / Response schemas (service-local) ──


class RegisterRequest(BaseModel):
    email: EmailStr
    full_name: str = Field(..., max_length=255)
    password: str = Field(..., min_length=8)
    org_id: uuid.UUID
    phone: str | None = None
    user_type: UserType = UserType.CUSTOMER
    timezone: str = "UTC"
    locale: str = "en-US"


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class ProfileUpdateRequest(BaseModel):
    full_name: str | None = None
    phone: str | None = None
    timezone: str | None = None
    locale: str | None = None
    avatar_url: str | None = None


# ── JWT Helpers ──


def _create_token(data: dict[str, Any], expires_delta: timedelta) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        **data,
        "iat": int(now.timestamp()),
        "exp": int((now + expires_delta).timestamp()),
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def create_access_token(user_id: str, org_id: str, user_type: str) -> str:
    return _create_token(
        {"sub": user_id, "org_id": org_id, "user_type": user_type},
        timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )


def create_refresh_token(user_id: str, org_id: str, user_type: str) -> str:
    return _create_token(
        {"sub": user_id, "org_id": org_id, "user_type": user_type, "refresh": True},
        timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
    )


def decode_token(token: str) -> dict[str, Any]:
    """Decode and validate a JWT.  Raises HTTPException on failure."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if "sub" not in payload:
            raise HTTPException(status_code=401, detail="Invalid token payload")
        return payload
    except JWTError as exc:
        raise HTTPException(
            status_code=401,
            detail=f"Token validation failed: {exc}",
        )


# ── Auth dependencies ──


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Extract and validate the current user from the Bearer token."""
    if credentials is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    payload = decode_token(credentials.credentials)
    user_id = payload["sub"]

    result = await db.execute(
        text(
            "SELECT id, org_id, email, full_name, phone, user_type, status, "
            "avatar_url, timezone, locale, last_login_at, created_at, updated_at "
            "FROM users WHERE id = :uid"
        ),
        {"uid": user_id},
    )
    row = result.mappings().first()
    if row is None:
        raise HTTPException(status_code=401, detail="User not found")
    if row["status"] != UserStatus.ACTIVE.value:
        raise HTTPException(status_code=403, detail="User account is not active")
    return dict(row)


def require_roles(*allowed_roles: str):
    """Dependency factory that enforces role-based access control."""

    async def _check(current_user: dict[str, Any] = Depends(get_current_user)):
        if current_user["user_type"] not in allowed_roles:
            raise HTTPException(
                status_code=403,
                detail=f"Role '{current_user['user_type']}' is not authorized for this action",
            )
        return current_user

    return _check


# ── Row → Pydantic helper ──


def _user_response(row: dict[str, Any]) -> UserResponse:
    return UserResponse(
        id=row["id"],
        org_id=row["org_id"],
        email=row["email"],
        full_name=row["full_name"],
        phone=row.get("phone"),
        user_type=row["user_type"],
        status=row.get("status", UserStatus.ACTIVE),
        avatar_url=row.get("avatar_url"),
        timezone=row.get("timezone", "UTC"),
        locale=row.get("locale", "en-US"),
        last_login_at=row.get("last_login_at"),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


# ── Lifespan ──


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Auth service starting up …")
    # Warm up DB connection pool
    async with engine.begin() as conn:
        await conn.execute(text("SELECT 1"))
    logger.info("Database connection OK")

    # Warm up Redis
    redis = await get_redis()
    await redis.ping()
    logger.info("Redis connection OK")

    yield

    logger.info("Auth service shutting down …")
    await close_redis()
    await engine.dispose()


# ── FastAPI app ──

app = FastAPI(
    title="Auth Service",
    version="1.0.0",
    description="Authentication & user management microservice",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from shared.utils.metrics import setup_metrics
setup_metrics(app)


# ── Health ──


@app.get("/health", tags=["health"])
async def health_check():
    return {"status": "healthy", "service": "auth-service", "timestamp": datetime.now(timezone.utc).isoformat()}


# ── Register ──


@app.post(
    "/api/v1/auth/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["auth"],
)
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """Register a new user."""
    # Check that org exists
    org = await db.execute(
        text("SELECT id FROM organizations WHERE id = :oid AND is_active = true"),
        {"oid": str(body.org_id)},
    )
    if org.first() is None:
        raise HTTPException(status_code=404, detail="Organization not found")

    # Check duplicate email within org
    dup = await db.execute(
        text("SELECT id FROM users WHERE email = :email AND org_id = :oid"),
        {"email": body.email, "oid": str(body.org_id)},
    )
    if dup.first() is not None:
        raise HTTPException(status_code=409, detail="Email already registered in this organization")

    user_id = uuid.uuid4()
    hashed = pwd_context.hash(body.password)
    now = datetime.now(timezone.utc)

    await db.execute(
        text(
            """
            INSERT INTO users (id, org_id, email, full_name, phone, user_type,
                               password_hash, status, timezone, locale, created_at, updated_at)
            VALUES (:id, :org_id, :email, :full_name, :phone, :user_type,
                    :password_hash, :status, :tz, :locale, :now, :now)
            """
        ),
        {
            "id": str(user_id),
            "org_id": str(body.org_id),
            "email": body.email,
            "full_name": body.full_name,
            "phone": body.phone,
            "user_type": body.user_type.value,
            "password_hash": hashed,
            "status": UserStatus.ACTIVE.value,
            "tz": body.timezone,
            "locale": body.locale,
            "now": now,
        },
    )

    logger.info("Registered user %s (%s) in org %s", user_id, body.email, body.org_id)

    result = await db.execute(
        text(
            "SELECT id, org_id, email, full_name, phone, user_type, status, "
            "avatar_url, timezone, locale, last_login_at, created_at, updated_at "
            "FROM users WHERE id = :uid"
        ),
        {"uid": str(user_id)},
    )
    return _user_response(dict(result.mappings().one()))


# ── Login ──


@app.post("/api/v1/auth/login", response_model=TokenResponse, tags=["auth"])
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    """Authenticate a user and return JWT tokens."""
    result = await db.execute(
        text(
            "SELECT id, org_id, email, password_hash, user_type, status "
            "FROM users WHERE email = :email"
        ),
        {"email": body.email},
    )
    row = result.mappings().first()

    if row is None or not pwd_context.verify(body.password, row["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if row["status"] != UserStatus.ACTIVE.value:
        raise HTTPException(status_code=403, detail="Account is not active")

    user_id = str(row["id"])
    org_id = str(row["org_id"])
    user_type = row["user_type"]

    # Update last_login_at
    await db.execute(
        text("UPDATE users SET last_login_at = :now WHERE id = :uid"),
        {"now": datetime.now(timezone.utc), "uid": user_id},
    )

    access = create_access_token(user_id, org_id, user_type)
    refresh = create_refresh_token(user_id, org_id, user_type)

    # Store refresh token JTI in Redis for revocation support
    redis = await get_redis()
    refresh_payload = jwt.decode(refresh, SECRET_KEY, algorithms=[ALGORITHM])
    await redis.setex(
        f"refresh:{refresh_payload['jti']}",
        REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        user_id,
    )

    logger.info("User %s logged in", user_id)
    return TokenResponse(
        access_token=access,
        refresh_token=refresh,
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


# ── Refresh ──


@app.post("/api/v1/auth/refresh", response_model=TokenResponse, tags=["auth"])
async def refresh_token(body: RefreshRequest, db: AsyncSession = Depends(get_db)):
    """Issue a new access token from a valid refresh token."""
    payload = decode_token(body.refresh_token)
    if not payload.get("refresh"):
        raise HTTPException(status_code=400, detail="Not a refresh token")

    jti = payload.get("jti")
    redis = await get_redis()
    stored = await redis.get(f"refresh:{jti}")
    if stored is None:
        raise HTTPException(status_code=401, detail="Refresh token revoked or expired")

    user_id = payload["sub"]
    org_id = payload["org_id"]
    user_type = payload["user_type"]

    # Verify user still exists and is active
    result = await db.execute(
        text("SELECT status FROM users WHERE id = :uid"),
        {"uid": user_id},
    )
    row = result.mappings().first()
    if row is None or row["status"] != UserStatus.ACTIVE.value:
        raise HTTPException(status_code=401, detail="User account unavailable")

    # Rotate: revoke old, issue new
    await redis.delete(f"refresh:{jti}")

    new_access = create_access_token(user_id, org_id, user_type)
    new_refresh = create_refresh_token(user_id, org_id, user_type)

    new_refresh_payload = jwt.decode(new_refresh, SECRET_KEY, algorithms=[ALGORITHM])
    await redis.setex(
        f"refresh:{new_refresh_payload['jti']}",
        REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        user_id,
    )

    logger.info("Token refreshed for user %s", user_id)
    return TokenResponse(
        access_token=new_access,
        refresh_token=new_refresh,
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


# ── Get current user ──


@app.get("/api/v1/auth/me", response_model=UserResponse, tags=["auth"])
async def get_me(current_user: dict[str, Any] = Depends(get_current_user)):
    """Return the profile of the authenticated user."""
    return _user_response(current_user)


# ── Update current user ──


@app.put("/api/v1/auth/me", response_model=UserResponse, tags=["auth"])
async def update_me(
    body: ProfileUpdateRequest,
    current_user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update the authenticated user's profile."""
    updates: dict[str, Any] = {}
    if body.full_name is not None:
        updates["full_name"] = body.full_name
    if body.phone is not None:
        updates["phone"] = body.phone
    if body.timezone is not None:
        updates["timezone"] = body.timezone
    if body.locale is not None:
        updates["locale"] = body.locale
    if body.avatar_url is not None:
        updates["avatar_url"] = body.avatar_url

    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    updates["updated_at"] = datetime.now(timezone.utc)
    set_clause = ", ".join(f"{k} = :{k}" for k in updates)
    updates["uid"] = str(current_user["id"])

    await db.execute(
        text(f"UPDATE users SET {set_clause} WHERE id = :uid"),  # noqa: S608
        updates,
    )

    result = await db.execute(
        text(
            "SELECT id, org_id, email, full_name, phone, user_type, status, "
            "avatar_url, timezone, locale, last_login_at, created_at, updated_at "
            "FROM users WHERE id = :uid"
        ),
        {"uid": str(current_user["id"])},
    )
    logger.info("User %s profile updated", current_user["id"])
    return _user_response(dict(result.mappings().one()))


# ── List users (admin only) ──


@app.get("/api/v1/auth/users", response_model=PaginatedResponse, tags=["admin"])
async def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: UserStatus | None = Query(None, alias="status"),
    user_type_filter: UserType | None = Query(None, alias="user_type"),
    current_user: dict[str, Any] = Depends(
        require_roles(UserType.ADMIN.value, UserType.SUPERADMIN.value)
    ),
    db: AsyncSession = Depends(get_db),
):
    """List users in the same organization (admin / superadmin only)."""
    org_id = str(current_user["org_id"])
    conditions = ["org_id = :org_id"]
    params: dict[str, Any] = {"org_id": org_id}

    if status_filter is not None:
        conditions.append("status = :status")
        params["status"] = status_filter.value
    if user_type_filter is not None:
        conditions.append("user_type = :user_type")
        params["user_type"] = user_type_filter.value

    where = " AND ".join(conditions)

    # Total count
    count_result = await db.execute(text(f"SELECT count(*) FROM users WHERE {where}"), params)  # noqa: S608
    total = count_result.scalar_one()

    offset = (page - 1) * page_size
    params["limit"] = page_size
    params["offset"] = offset

    rows_result = await db.execute(
        text(
            f"SELECT id, org_id, email, full_name, phone, user_type, status, "  # noqa: S608
            f"avatar_url, timezone, locale, last_login_at, created_at, updated_at "
            f"FROM users WHERE {where} ORDER BY created_at DESC LIMIT :limit OFFSET :offset"
        ),
        params,
    )
    users = [_user_response(dict(r)) for r in rows_result.mappings().all()]
    total_pages = max(1, -(-total // page_size))  # ceil div

    return PaginatedResponse(
        items=users,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


# ── Run ──

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8002")),
        reload=os.getenv("RELOAD", "true").lower() == "true",
        log_level="info",
    )
