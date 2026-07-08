from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "AccessHub"
    debug: bool = False
    database_url: str = "postgresql+asyncpg://accesshub:accesshub@db:5432/accesshub"
    redis_url: str = "redis://redis:6379/0"

    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7


# jwt_secret_key обязателен, но приходит из окружения, а не из вызова конструктора —
# mypy не умеет это учитывать
settings = Settings()  # type: ignore[call-arg]
