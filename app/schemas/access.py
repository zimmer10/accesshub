from pydantic import BaseModel


class AccessCheckResponse(BaseModel):
    user_id: int
    permission: str
    allowed: bool


class EffectivePermissionsResponse(BaseModel):
    user_id: int
    groups: list[int]
    ancestor_groups: list[int]
    roles: list[int]
    permissions: list[str]
