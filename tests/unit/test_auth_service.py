"""Unit tests for the Auth Service endpoints.

Tests cover: health, register, login, refresh, get-me, update-me, list-users, RBAC.
All database calls are mocked — no external services required.
"""

from __future__ import annotations

import os
import sys
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

# Ensure project root is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

TEST_SECRET = "test-secret-key-for-testing-only"
os.environ["JWT_SECRET_KEY"] = TEST_SECRET
os.environ["DATABASE_URL"] = "sqlite+aiosqlite://"
os.environ["REDIS_URL"] = "redis://localhost:6379/0"

from tests.conftest import (
    FakeRedis,
    MockDBSession,
    MockResult,
    TEST_ADMIN_ID,
    TEST_ORG_ID,
    TEST_USER_ID,
    make_token,
    make_user_row,
)


# ── Patch shared module before importing the service ──

_fake_redis = FakeRedis()
_mock_db = MockDBSession()

import shared.utils.database


@pytest_asyncio.fixture
async def client():
    """Create a test client with mocked dependencies."""
    global _mock_db, _fake_redis
    _mock_db = MockDBSession()
    _fake_redis = FakeRedis()

    # Patch database module before import
    with patch("shared.utils.database.engine") as mock_engine, \
         patch("shared.utils.database.get_redis", return_value=_fake_redis), \
         patch("shared.utils.database.close_redis"):

        # Mock engine for lifespan
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock()
        mock_engine.begin.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_engine.begin.return_value.__aexit__ = AsyncMock()
        mock_engine.dispose = AsyncMock()
        auth_service_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../services/auth-service"))
        if auth_service_dir not in sys.path:
            sys.path.insert(0, auth_service_dir)
        if "main" in sys.modules:
            del sys.modules["main"]
        import main as auth_mod
        auth_mod.SECRET_KEY = TEST_SECRET
        app = auth_mod.app

        # Override get_db
        async def override_get_db():
            yield _mock_db

        async def override_get_redis():
            return _fake_redis

        from shared.utils.database import get_db
        app.dependency_overrides[get_db] = override_get_db

        # Also patch get_redis in the auth module
        auth_mod.get_redis = override_get_redis

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            yield c

        app.dependency_overrides.clear()


# ── Health ──


@pytest.mark.asyncio
async def test_health_check(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert data["service"] == "auth-service"


# ── Register ──


@pytest.mark.asyncio
async def test_register_success(client):
    now = datetime.now(timezone.utc)
    user_row = make_user_row()

    # Queue: org check → dup check → insert → select
    _mock_db.queue_result(MockResult(rows=[{"id": TEST_ORG_ID}]))  # org exists
    _mock_db.queue_result(MockResult(rows=[]))  # no duplicate
    _mock_db.queue_result(MockResult())  # insert
    _mock_db.queue_result(MockResult(rows=[user_row]))  # select back

    resp = await client.post("/api/v1/auth/register", json={
        "email": "new@example.com",
        "full_name": "New User",
        "password": "strongpass123",
        "org_id": TEST_ORG_ID,
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["email"] == "test@example.com"  # from mock row


@pytest.mark.asyncio
async def test_register_duplicate_email(client):
    _mock_db.queue_result(MockResult(rows=[{"id": TEST_ORG_ID}]))  # org exists
    _mock_db.queue_result(MockResult(rows=[{"id": "existing"}]))  # duplicate!

    resp = await client.post("/api/v1/auth/register", json={
        "email": "dup@example.com",
        "full_name": "Dup User",
        "password": "strongpass123",
        "org_id": TEST_ORG_ID,
    })
    assert resp.status_code == 409
    assert "already registered" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_register_invalid_org(client):
    _mock_db.queue_result(MockResult(rows=[]))  # org NOT found

    resp = await client.post("/api/v1/auth/register", json={
        "email": "test@example.com",
        "full_name": "Test",
        "password": "strongpass123",
        "org_id": TEST_ORG_ID,
    })
    assert resp.status_code == 404
    assert "Organization" in resp.json()["detail"]


# ── Login ──


@pytest.mark.asyncio
async def test_login_success(client):
    from passlib.context import CryptContext
    pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")
    hashed = pwd.hash("correctpassword")

    user_row = {
        "id": TEST_USER_ID,
        "org_id": TEST_ORG_ID,
        "email": "test@example.com",
        "password_hash": hashed,
        "user_type": "customer",
        "status": "active",
    }

    _mock_db.queue_result(MockResult(rows=[user_row]))  # find user
    _mock_db.queue_result(MockResult())  # update last_login_at

    resp = await client.post("/api/v1/auth/login", json={
        "email": "test@example.com",
        "password": "correctpassword",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["expires_in"] > 0


@pytest.mark.asyncio
async def test_login_wrong_password(client):
    from passlib.context import CryptContext
    pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")
    hashed = pwd.hash("correctpassword")

    _mock_db.queue_result(MockResult(rows=[{
        "id": TEST_USER_ID,
        "org_id": TEST_ORG_ID,
        "email": "test@example.com",
        "password_hash": hashed,
        "user_type": "customer",
        "status": "active",
    }]))

    resp = await client.post("/api/v1/auth/login", json={
        "email": "test@example.com",
        "password": "wrongpassword",
    })
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_login_unknown_user(client):
    _mock_db.queue_result(MockResult(rows=[]))  # no user found

    resp = await client.post("/api/v1/auth/login", json={
        "email": "unknown@example.com",
        "password": "anypass",
    })
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_login_inactive_account(client):
    from passlib.context import CryptContext
    pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")

    _mock_db.queue_result(MockResult(rows=[{
        "id": TEST_USER_ID,
        "org_id": TEST_ORG_ID,
        "email": "test@example.com",
        "password_hash": pwd.hash("pass123"),
        "user_type": "customer",
        "status": "suspended",
    }]))

    resp = await client.post("/api/v1/auth/login", json={
        "email": "test@example.com",
        "password": "pass123",
    })
    assert resp.status_code == 403


# ── Get Me ──


@pytest.mark.asyncio
async def test_get_me_authenticated(client):
    user_row = make_user_row()
    _mock_db.queue_result(MockResult(rows=[user_row]))

    token = make_token(user_type="customer")
    resp = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["email"] == "test@example.com"


@pytest.mark.asyncio
async def test_get_me_no_token(client):
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_me_invalid_token(client):
    resp = await client.get("/api/v1/auth/me", headers={"Authorization": "Bearer invalid.token.here"})
    assert resp.status_code == 401


# ── Update Profile ──


@pytest.mark.asyncio
async def test_update_profile(client):
    user_row = make_user_row()
    updated_row = {**user_row, "full_name": "Updated Name"}

    _mock_db.queue_result(MockResult(rows=[user_row]))  # get_current_user
    _mock_db.queue_result(MockResult())  # update
    _mock_db.queue_result(MockResult(rows=[updated_row]))  # select back

    token = make_token(user_type="customer")
    resp = await client.put(
        "/api/v1/auth/me",
        json={"full_name": "Updated Name"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200


# ── List Users (admin RBAC) ──


@pytest.mark.asyncio
async def test_list_users_admin_only(client):
    admin_row = make_user_row(user_id=TEST_ADMIN_ID, user_type="admin")

    _mock_db.queue_result(MockResult(rows=[admin_row]))  # get_current_user
    _mock_db.queue_result(MockResult(scalar=1))  # count
    _mock_db.queue_result(MockResult(rows=[admin_row]))  # user rows

    token = make_token(user_id=TEST_ADMIN_ID, user_type="admin")
    resp = await client.get("/api/v1/auth/users", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert data["total"] == 1


@pytest.mark.asyncio
async def test_list_users_non_admin_forbidden(client):
    user_row = make_user_row(user_type="customer")
    _mock_db.queue_result(MockResult(rows=[user_row]))

    token = make_token(user_type="customer")
    resp = await client.get("/api/v1/auth/users", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403


# ── Refresh Token ──


@pytest.mark.asyncio
async def test_refresh_token_success(client):
    refresh = make_token(user_type="customer", is_refresh=True)

    # Store refresh JTI in fake redis
    from jose import jwt as jose_jwt
    payload = jose_jwt.decode(refresh, TEST_SECRET, algorithms=["HS256"])
    await _fake_redis.setex(f"refresh:{payload['jti']}", 86400, TEST_USER_ID)

    # Mock DB: user status check
    _mock_db.queue_result(MockResult(rows=[{"status": "active"}]))

    resp = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh})
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data
