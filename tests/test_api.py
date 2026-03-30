import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_health_check(client: AsyncClient):
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

@pytest.mark.asyncio
async def test_login_and_get_me(client: AsyncClient):
    # 1. Login (Create User)
    login_data = {"firebase_uid": "test_uid_123", "email": "test@example.com"}
    response = await client.post("/api/v1/auth/login", json=login_data)
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "test@example.com"
    assert "user_id" in data

    # 2. Get Me (Auth)
    headers = {"Authorization": "Bearer test_uid_123"}
    response = await client.get("/api/v1/auth/me", headers=headers)
    assert response.status_code == 200
    assert response.json()["email"] == "test@example.com"

@pytest.mark.asyncio
async def test_get_gamification_stats(client: AsyncClient):
    # Setup user
    login_data = {"firebase_uid": "gamer_1", "email": "gamer@pelvia.com"}
    await client.post("/api/v1/auth/login", json=login_data)
    
    headers = {"Authorization": "Bearer gamer_1"}
    response = await client.get("/api/v1/gamification/stats", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert "xp" in data
    assert "streak" in data
