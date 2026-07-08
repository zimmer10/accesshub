import redis.asyncio as redis
from httpx import AsyncClient


async def test_access_check_uses_cache_on_second_call(
    client: AsyncClient, auth_headers: dict[str, str], redis_client: redis.Redis
) -> None:
    user = await client.post(
        "/users",
        json={"username": "cache1", "email": "cache1@example.com", "password": "password123"},
        headers=auth_headers,
    )
    user_id = user.json()["id"]

    first = await client.get(
        "/access/check",
        params={"user_id": user_id, "permission": "cache:read"},
        headers=auth_headers,
    )
    assert first.json()["allowed"] is False

    # напрямую переворачиваем значение, которое эндпоинт только что закэшировал —
    # если check_access реально читает из Redis, а не пересчитывает каждый раз,
    # второй ответ будет "неправильным" (True), и это доказывает, что кэш read-path
    # действительно используется
    await redis_client.set(f"perm:{user_id}:cache:read", "1", ex=60)

    second = await client.get(
        "/access/check",
        params={"user_id": user_id, "permission": "cache:read"},
        headers=auth_headers,
    )
    assert second.json()["allowed"] is True


async def test_granting_direct_role_invalidates_stale_cache(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    user = await client.post(
        "/users",
        json={"username": "cache2", "email": "cache2@example.com", "password": "password123"},
        headers=auth_headers,
    )
    user_id = user.json()["id"]
    role = await client.post("/roles", json={"name": "cache-role"}, headers=auth_headers)
    role_id = role.json()["id"]
    permission = await client.post(
        "/permissions", json={"code": "cache:direct"}, headers=auth_headers
    )
    permission_id = permission.json()["id"]
    await client.post(
        f"/roles/{role_id}/permissions",
        json={"permission_id": permission_id},
        headers=auth_headers,
    )

    denied = await client.get(
        "/access/check",
        params={"user_id": user_id, "permission": "cache:direct"},
        headers=auth_headers,
    )
    assert denied.json()["allowed"] is False  # это значение уже закэшировано

    await client.post(f"/users/{user_id}/roles", json={"role_id": role_id}, headers=auth_headers)

    allowed = await client.get(
        "/access/check",
        params={"user_id": user_id, "permission": "cache:direct"},
        headers=auth_headers,
    )
    assert allowed.json()["allowed"] is True  # не залипло на закэшированном False


async def test_group_role_change_invalidates_cache_for_members(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    group = await client.post("/groups", json={"name": "CacheGroup"}, headers=auth_headers)
    group_id = group.json()["id"]
    user = await client.post(
        "/users",
        json={"username": "cache3", "email": "cache3@example.com", "password": "password123"},
        headers=auth_headers,
    )
    user_id = user.json()["id"]
    await client.post(
        f"/groups/{group_id}/members", json={"user_id": user_id}, headers=auth_headers
    )

    role = await client.post("/roles", json={"name": "cache-group-role"}, headers=auth_headers)
    role_id = role.json()["id"]
    permission = await client.post(
        "/permissions", json={"code": "cache:group"}, headers=auth_headers
    )
    permission_id = permission.json()["id"]
    await client.post(
        f"/roles/{role_id}/permissions",
        json={"permission_id": permission_id},
        headers=auth_headers,
    )

    denied = await client.get(
        "/access/check",
        params={"user_id": user_id, "permission": "cache:group"},
        headers=auth_headers,
    )
    assert denied.json()["allowed"] is False

    await client.post(f"/groups/{group_id}/roles", json={"role_id": role_id}, headers=auth_headers)

    allowed = await client.get(
        "/access/check",
        params={"user_id": user_id, "permission": "cache:group"},
        headers=auth_headers,
    )
    assert allowed.json()["allowed"] is True


async def test_reparenting_group_invalidates_cache_for_descendant_members(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    new_parent = await client.post("/groups", json={"name": "NewParent"}, headers=auth_headers)
    new_parent_id = new_parent.json()["id"]
    old_parent = await client.post("/groups", json={"name": "OldParent"}, headers=auth_headers)
    old_parent_id = old_parent.json()["id"]
    child = await client.post(
        "/groups",
        json={"name": "MovingChild", "parent_group_id": old_parent_id},
        headers=auth_headers,
    )
    child_id = child.json()["id"]

    user = await client.post(
        "/users",
        json={"username": "cache4", "email": "cache4@example.com", "password": "password123"},
        headers=auth_headers,
    )
    user_id = user.json()["id"]
    await client.post(
        f"/groups/{child_id}/members", json={"user_id": user_id}, headers=auth_headers
    )

    role = await client.post("/roles", json={"name": "cache-reparent-role"}, headers=auth_headers)
    role_id = role.json()["id"]
    permission = await client.post(
        "/permissions", json={"code": "cache:reparent"}, headers=auth_headers
    )
    permission_id = permission.json()["id"]
    await client.post(
        f"/roles/{role_id}/permissions",
        json={"permission_id": permission_id},
        headers=auth_headers,
    )
    await client.post(
        f"/groups/{new_parent_id}/roles", json={"role_id": role_id}, headers=auth_headers
    )

    denied = await client.get(
        "/access/check",
        params={"user_id": user_id, "permission": "cache:reparent"},
        headers=auth_headers,
    )
    assert denied.json()["allowed"] is False  # ребёнок пока под старым родителем

    await client.patch(
        f"/groups/{child_id}",
        json={"parent_group_id": new_parent_id},
        headers=auth_headers,
    )

    allowed = await client.get(
        "/access/check",
        params={"user_id": user_id, "permission": "cache:reparent"},
        headers=auth_headers,
    )
    assert allowed.json()["allowed"] is True
