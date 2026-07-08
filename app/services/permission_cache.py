import redis.asyncio as redis

CACHE_TTL_SECONDS = 60


def _access_check_key(user_id: int, permission_code: str) -> str:
    return f"perm:{user_id}:{permission_code}"


def _user_cache_keys_key(user_id: int) -> str:
    return f"user_cache_keys:{user_id}"


async def get_cached_access_check(
    redis_client: redis.Redis, user_id: int, permission_code: str
) -> bool | None:
    value = await redis_client.get(_access_check_key(user_id, permission_code))
    if value is None:
        return None
    return value == "1"


async def set_cached_access_check(
    redis_client: redis.Redis, user_id: int, permission_code: str, allowed: bool
) -> None:
    key = _access_check_key(user_id, permission_code)
    await redis_client.set(key, "1" if allowed else "0", ex=CACHE_TTL_SECONDS)
    # регистрируем ключ в персональном set'е пользователя, чтобы при инвалидации
    # не делать дорогой SCAN по всем ключам redis — только SMEMBERS + DEL
    await redis_client.sadd(_user_cache_keys_key(user_id), key)


async def invalidate_user_cache(redis_client: redis.Redis, user_id: int) -> None:
    set_key = _user_cache_keys_key(user_id)
    keys = await redis_client.smembers(set_key)
    if keys:
        await redis_client.delete(*keys)
    await redis_client.delete(set_key)


async def invalidate_users_cache(redis_client: redis.Redis, user_ids: set[int]) -> None:
    for user_id in user_ids:
        await invalidate_user_cache(redis_client, user_id)
