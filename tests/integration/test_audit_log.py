from httpx import AsyncClient

from app.core.security import decode_token


def _actor_id_from_headers(headers: dict[str, str]) -> int:
    token = headers["Authorization"].removeprefix("Bearer ")
    return decode_token(token, expected_type="access")


async def test_create_user_writes_audit_log_entry(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    response = await client.post(
        "/users",
        json={"username": "logged1", "email": "logged1@example.com", "password": "password123"},
        headers=auth_headers,
    )
    user_id = response.json()["id"]

    log = await client.get("/audit-log", headers=auth_headers)
    assert log.status_code == 200

    entries = [
        entry
        for entry in log.json()
        if entry["action"] == "user.create" and entry["target_id"] == user_id
    ]
    assert len(entries) == 1
    entry = entries[0]
    assert entry["target_type"] == "user"
    assert entry["before"] is None
    assert entry["after"]["username"] == "logged1"
    assert "hashed_password" not in entry["after"]
    assert "password" not in entry["after"]


async def test_password_change_never_logs_the_password(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    create = await client.post(
        "/users",
        json={"username": "logged2", "email": "logged2@example.com", "password": "password123"},
        headers=auth_headers,
    )
    user_id = create.json()["id"]

    await client.patch(
        f"/users/{user_id}", json={"password": "brandNewSecret456"}, headers=auth_headers
    )

    log = await client.get("/audit-log", headers=auth_headers)
    entries = [
        entry
        for entry in log.json()
        if entry["action"] == "user.update" and entry["target_id"] == user_id
    ]
    assert len(entries) == 1
    entry = entries[0]
    assert entry["after"]["password_changed"] is True

    raw_body = log.text
    assert "brandNewSecret456" not in raw_body


async def test_delete_role_logs_before_snapshot(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    role = await client.post(
        "/roles", json={"name": "audited-role", "description": "temp"}, headers=auth_headers
    )
    role_id = role.json()["id"]

    await client.delete(f"/roles/{role_id}", headers=auth_headers)

    log = await client.get("/audit-log", headers=auth_headers)
    entries = [
        entry
        for entry in log.json()
        if entry["action"] == "role.delete" and entry["target_id"] == role_id
    ]
    assert len(entries) == 1
    assert entries[0]["before"]["name"] == "audited-role"
    assert entries[0]["after"] is None


async def test_audit_log_filters_by_user_id(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    actor_id = _actor_id_from_headers(auth_headers)
    await client.post("/permissions", json={"code": "audit:filter-test"}, headers=auth_headers)

    log = await client.get("/audit-log", params={"user_id": actor_id}, headers=auth_headers)
    assert log.status_code == 200
    assert all(entry["actor_id"] == actor_id for entry in log.json())

    other = await client.get("/audit-log", params={"user_id": 999999}, headers=auth_headers)
    assert other.json() == []


async def test_audit_log_date_from_in_the_future_returns_nothing(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    await client.post("/permissions", json={"code": "audit:date-test"}, headers=auth_headers)

    response = await client.get(
        "/audit-log", params={"date_from": "2999-01-01T00:00:00Z"}, headers=auth_headers
    )

    assert response.json() == []
