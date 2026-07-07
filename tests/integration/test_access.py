from httpx import AsyncClient


async def _create_permission(client: AsyncClient, headers: dict[str, str], code: str) -> int:
    response = await client.post("/permissions", json={"code": code}, headers=headers)
    return int(response.json()["id"])


async def _create_role(client: AsyncClient, headers: dict[str, str], name: str) -> int:
    response = await client.post("/roles", json={"name": name}, headers=headers)
    return int(response.json()["id"])


async def _create_group(
    client: AsyncClient, headers: dict[str, str], name: str, parent_group_id: int | None = None
) -> int:
    response = await client.post(
        "/groups", json={"name": name, "parent_group_id": parent_group_id}, headers=headers
    )
    return int(response.json()["id"])


async def test_access_check_via_direct_role(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    user = await client.post(
        "/users",
        json={"username": "alice1", "email": "alice1@example.com", "password": "password123"},
        headers=auth_headers,
    )
    user_id = user.json()["id"]

    role_id = await _create_role(client, auth_headers, "billing")
    permission_id = await _create_permission(client, auth_headers, "invoice:read")
    await client.post(
        f"/roles/{role_id}/permissions",
        json={"permission_id": permission_id},
        headers=auth_headers,
    )
    await client.post(f"/users/{user_id}/roles", json={"role_id": role_id}, headers=auth_headers)

    allowed = await client.get(
        "/access/check",
        params={"user_id": user_id, "permission": "invoice:read"},
        headers=auth_headers,
    )
    denied = await client.get(
        "/access/check",
        params={"user_id": user_id, "permission": "invoice:write"},
        headers=auth_headers,
    )

    assert allowed.json()["allowed"] is True
    assert denied.json()["allowed"] is False


async def test_access_check_via_group_role(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    user = await client.post(
        "/users",
        json={"username": "bob1", "email": "bob1@example.com", "password": "password123"},
        headers=auth_headers,
    )
    user_id = user.json()["id"]

    group_id = await _create_group(client, auth_headers, "Support")
    role_id = await _create_role(client, auth_headers, "support-agent")
    permission_id = await _create_permission(client, auth_headers, "ticket:read")
    await client.post(
        f"/roles/{role_id}/permissions",
        json={"permission_id": permission_id},
        headers=auth_headers,
    )
    await client.post(
        f"/groups/{group_id}/members", json={"user_id": user_id}, headers=auth_headers
    )
    await client.post(f"/groups/{group_id}/roles", json={"role_id": role_id}, headers=auth_headers)

    allowed = await client.get(
        "/access/check",
        params={"user_id": user_id, "permission": "ticket:read"},
        headers=auth_headers,
    )

    assert allowed.json()["allowed"] is True


async def test_access_check_not_found_user(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    response = await client.get(
        "/access/check",
        params={"user_id": 999999, "permission": "invoice:read"},
        headers=auth_headers,
    )

    assert response.status_code == 404


async def test_effective_permissions_through_nested_groups(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    user = await client.post(
        "/users",
        json={"username": "carol1", "email": "carol1@example.com", "password": "password123"},
        headers=auth_headers,
    )
    user_id = user.json()["id"]

    parent_group_id = await _create_group(client, auth_headers, "Org")
    child_group_id = await _create_group(client, auth_headers, "Team", parent_group_id)

    role_id = await _create_role(client, auth_headers, "org-admin")
    permission_id = await _create_permission(client, auth_headers, "org:*")
    await client.post(
        f"/roles/{role_id}/permissions",
        json={"permission_id": permission_id},
        headers=auth_headers,
    )
    # роль выдана родительской группе, пользователь состоит только в дочерней —
    # право должно резолвиться через обход иерархии вверх
    await client.post(
        f"/groups/{parent_group_id}/roles", json={"role_id": role_id}, headers=auth_headers
    )
    await client.post(
        f"/groups/{child_group_id}/members", json={"user_id": user_id}, headers=auth_headers
    )

    response = await client.get(f"/users/{user_id}/effective-permissions", headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["groups"] == [child_group_id]
    assert body["ancestor_groups"] == [parent_group_id]
    assert body["roles"] == [role_id]
    assert body["permissions"] == ["org:*"]

    allowed = await client.get(
        "/access/check",
        params={"user_id": user_id, "permission": "org:anything"},
        headers=auth_headers,
    )
    assert allowed.json()["allowed"] is True


async def test_update_group_parent_rejects_cycle(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    a_id = await _create_group(client, auth_headers, "A")
    b_id = await _create_group(client, auth_headers, "B", a_id)  # B's parent is A

    # попытка сделать A ребёнком B закольцевала бы иерархию: A -> B -> A
    response = await client.patch(
        f"/groups/{a_id}", json={"parent_group_id": b_id}, headers=auth_headers
    )

    assert response.status_code == 400
