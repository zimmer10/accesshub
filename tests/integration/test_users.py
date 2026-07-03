from httpx import AsyncClient


async def test_list_users_requires_authentication(client: AsyncClient) -> None:
    response = await client.get("/users")

    assert response.status_code == 401


async def test_create_and_get_user(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    response = await client.post(
        "/users",
        json={"username": "bob", "email": "bob@example.com", "password": "password123"},
        headers=auth_headers,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["username"] == "bob"

    response = await client.get(f"/users/{body['id']}", headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["email"] == "bob@example.com"


async def test_create_user_duplicate_conflict(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    payload = {"username": "carol", "email": "carol@example.com", "password": "password123"}
    first = await client.post("/users", json=payload, headers=auth_headers)
    assert first.status_code == 201

    second = await client.post("/users", json=payload, headers=auth_headers)

    assert second.status_code == 409


async def test_get_user_not_found(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    response = await client.get("/users/999999", headers=auth_headers)

    assert response.status_code == 404


async def test_update_user_partial(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    create = await client.post(
        "/users",
        json={"username": "dave", "email": "dave@example.com", "password": "password123"},
        headers=auth_headers,
    )
    user_id = create.json()["id"]

    response = await client.patch(
        f"/users/{user_id}", json={"is_active": False}, headers=auth_headers
    )

    assert response.status_code == 200
    body = response.json()
    assert body["is_active"] is False
    assert body["username"] == "dave"


async def test_update_user_conflicting_email(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    await client.post(
        "/users",
        json={"username": "erin", "email": "erin@example.com", "password": "password123"},
        headers=auth_headers,
    )
    create = await client.post(
        "/users",
        json={"username": "frank", "email": "frank@example.com", "password": "password123"},
        headers=auth_headers,
    )
    user_id = create.json()["id"]

    response = await client.patch(
        f"/users/{user_id}", json={"email": "erin@example.com"}, headers=auth_headers
    )

    assert response.status_code == 409


async def test_delete_user(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    create = await client.post(
        "/users",
        json={"username": "grace", "email": "grace@example.com", "password": "password123"},
        headers=auth_headers,
    )
    user_id = create.json()["id"]

    response = await client.delete(f"/users/{user_id}", headers=auth_headers)
    assert response.status_code == 204

    response = await client.get(f"/users/{user_id}", headers=auth_headers)
    assert response.status_code == 404
