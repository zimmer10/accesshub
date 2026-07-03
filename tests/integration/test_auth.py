from httpx import AsyncClient


async def test_register_login_refresh_flow(client: AsyncClient) -> None:
    register = await client.post(
        "/auth/register",
        json={"username": "henry", "email": "henry@example.com", "password": "password123"},
    )
    assert register.status_code == 201

    login = await client.post("/auth/login", data={"username": "henry", "password": "password123"})
    assert login.status_code == 200
    tokens = login.json()
    assert tokens["token_type"] == "bearer"

    refreshed = await client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert refreshed.status_code == 200
    assert "access_token" in refreshed.json()


async def test_login_wrong_password_rejected(client: AsyncClient) -> None:
    await client.post(
        "/auth/register",
        json={"username": "iris", "email": "iris@example.com", "password": "password123"},
    )

    response = await client.post("/auth/login", data={"username": "iris", "password": "wrong"})

    assert response.status_code == 401


async def test_refresh_rejects_access_token(client: AsyncClient) -> None:
    await client.post(
        "/auth/register",
        json={"username": "jack", "email": "jack@example.com", "password": "password123"},
    )
    login = await client.post("/auth/login", data={"username": "jack", "password": "password123"})
    access_token = login.json()["access_token"]

    response = await client.post("/auth/refresh", json={"refresh_token": access_token})

    assert response.status_code == 401


async def test_protected_endpoint_rejects_garbage_token(client: AsyncClient) -> None:
    response = await client.get("/users", headers={"Authorization": "Bearer not-a-real-token"})

    assert response.status_code == 401
