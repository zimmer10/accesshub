from httpx import AsyncClient


async def test_create_group(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    response = await client.post("/groups", json={"name": "Engineering"}, headers=auth_headers)

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Engineering"
    assert body["parent_group_id"] is None


async def test_create_group_duplicate_name(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    await client.post("/groups", json={"name": "Sales"}, headers=auth_headers)

    response = await client.post("/groups", json={"name": "Sales"}, headers=auth_headers)

    assert response.status_code == 409


async def test_create_group_missing_parent(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    response = await client.post(
        "/groups", json={"name": "Backend", "parent_group_id": 999999}, headers=auth_headers
    )

    assert response.status_code == 404


async def test_create_nested_group(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    parent = await client.post("/groups", json={"name": "Org"}, headers=auth_headers)
    parent_id = parent.json()["id"]

    child = await client.post(
        "/groups", json={"name": "Team A", "parent_group_id": parent_id}, headers=auth_headers
    )

    assert child.status_code == 201
    assert child.json()["parent_group_id"] == parent_id


async def test_update_group_reject_self_parent(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    group = await client.post("/groups", json={"name": "Standalone"}, headers=auth_headers)
    group_id = group.json()["id"]

    response = await client.patch(
        f"/groups/{group_id}", json={"parent_group_id": group_id}, headers=auth_headers
    )

    assert response.status_code == 400


async def test_delete_group(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    group = await client.post("/groups", json={"name": "Temp"}, headers=auth_headers)
    group_id = group.json()["id"]

    response = await client.delete(f"/groups/{group_id}", headers=auth_headers)

    assert response.status_code == 204


async def test_add_and_remove_member(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    group = await client.post("/groups", json={"name": "Members"}, headers=auth_headers)
    group_id = group.json()["id"]

    user = await client.post(
        "/users",
        json={"username": "member1", "email": "member1@example.com", "password": "password123"},
        headers=auth_headers,
    )
    user_id = user.json()["id"]

    add = await client.post(
        f"/groups/{group_id}/members", json={"user_id": user_id}, headers=auth_headers
    )
    assert add.status_code == 204

    duplicate = await client.post(
        f"/groups/{group_id}/members", json={"user_id": user_id}, headers=auth_headers
    )
    assert duplicate.status_code == 409

    remove = await client.delete(f"/groups/{group_id}/members/{user_id}", headers=auth_headers)
    assert remove.status_code == 204

    remove_again = await client.delete(
        f"/groups/{group_id}/members/{user_id}", headers=auth_headers
    )
    assert remove_again.status_code == 404


async def test_assign_and_revoke_role(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    group = await client.post("/groups", json={"name": "RoleTarget"}, headers=auth_headers)
    group_id = group.json()["id"]
    role = await client.post("/roles", json={"name": "role-for-group"}, headers=auth_headers)
    role_id = role.json()["id"]

    add = await client.post(
        f"/groups/{group_id}/roles", json={"role_id": role_id}, headers=auth_headers
    )
    assert add.status_code == 204

    duplicate = await client.post(
        f"/groups/{group_id}/roles", json={"role_id": role_id}, headers=auth_headers
    )
    assert duplicate.status_code == 409

    remove = await client.delete(f"/groups/{group_id}/roles/{role_id}", headers=auth_headers)
    assert remove.status_code == 204

    remove_again = await client.delete(f"/groups/{group_id}/roles/{role_id}", headers=auth_headers)
    assert remove_again.status_code == 404


async def test_assign_role_missing_role_404(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    group = await client.post("/groups", json={"name": "GhostRoleTarget"}, headers=auth_headers)
    group_id = group.json()["id"]

    response = await client.post(
        f"/groups/{group_id}/roles", json={"role_id": 999999}, headers=auth_headers
    )

    assert response.status_code == 404
