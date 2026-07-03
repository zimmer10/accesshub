from httpx import AsyncClient


async def test_create_permission(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    response = await client.post(
        "/permissions",
        json={"code": "invoice:write", "description": "write invoices"},
        headers=auth_headers,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["code"] == "invoice:write"


async def test_create_permission_duplicate_code(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    await client.post("/permissions", json={"code": "invoice:delete"}, headers=auth_headers)

    response = await client.post(
        "/permissions", json={"code": "invoice:delete"}, headers=auth_headers
    )

    assert response.status_code == 409


async def test_list_permissions(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    await client.post("/permissions", json={"code": "report:read"}, headers=auth_headers)

    response = await client.get("/permissions", headers=auth_headers)

    assert response.status_code == 200
    codes = [p["code"] for p in response.json()]
    assert "report:read" in codes
