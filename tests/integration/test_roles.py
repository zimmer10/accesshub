from httpx import AsyncClient


async def test_create_role(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    response = await client.post(
        "/roles", json={"name": "admin", "description": "full access"}, headers=auth_headers
    )

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "admin"
    assert body["permissions"] == []


async def test_create_role_duplicate_name(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    await client.post("/roles", json={"name": "viewer"}, headers=auth_headers)

    response = await client.post("/roles", json={"name": "viewer"}, headers=auth_headers)

    assert response.status_code == 409


async def test_assign_permission_to_role(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    role = await client.post("/roles", json={"name": "editor"}, headers=auth_headers)
    role_id = role.json()["id"]
    permission = await client.post(
        "/permissions", json={"code": "invoice:read"}, headers=auth_headers
    )
    permission_id = permission.json()["id"]

    response = await client.post(
        f"/roles/{role_id}/permissions",
        json={"permission_id": permission_id},
        headers=auth_headers,
    )

    assert response.status_code == 204

    updated_role = await client.get(f"/roles/{role_id}", headers=auth_headers)
    codes = [p["code"] for p in updated_role.json()["permissions"]]
    assert codes == ["invoice:read"]


async def test_assign_permission_missing_permission_404(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    role = await client.post("/roles", json={"name": "ghost"}, headers=auth_headers)
    role_id = role.json()["id"]

    response = await client.post(
        f"/roles/{role_id}/permissions", json={"permission_id": 999999}, headers=auth_headers
    )

    assert response.status_code == 404


async def test_assign_permission_duplicate_conflict(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    role = await client.post("/roles", json={"name": "auditor"}, headers=auth_headers)
    role_id = role.json()["id"]
    permission = await client.post(
        "/permissions", json={"code": "audit:read"}, headers=auth_headers
    )
    permission_id = permission.json()["id"]

    first = await client.post(
        f"/roles/{role_id}/permissions",
        json={"permission_id": permission_id},
        headers=auth_headers,
    )
    assert first.status_code == 204

    second = await client.post(
        f"/roles/{role_id}/permissions",
        json={"permission_id": permission_id},
        headers=auth_headers,
    )

    assert second.status_code == 409


async def test_update_role(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    role = await client.post("/roles", json={"name": "temp-role"}, headers=auth_headers)
    role_id = role.json()["id"]

    response = await client.patch(
        f"/roles/{role_id}", json={"description": "updated"}, headers=auth_headers
    )

    assert response.status_code == 200
    assert response.json()["description"] == "updated"


async def test_delete_role(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    role = await client.post("/roles", json={"name": "throwaway"}, headers=auth_headers)
    role_id = role.json()["id"]

    response = await client.delete(f"/roles/{role_id}", headers=auth_headers)
    assert response.status_code == 204

    get_response = await client.get(f"/roles/{role_id}", headers=auth_headers)
    assert get_response.status_code == 404
