import os
from dataclasses import dataclass
from functools import lru_cache


@dataclass(frozen=True)
class Settings:
    database_url: str
    jwt_secret: str
    jwt_ttl_seconds: int
    secret_pepper: str
    environment: str


@lru_cache
def get_settings() -> Settings:
    return Settings(
        database_url=os.environ["DATABASE_URL"],
        jwt_secret=os.environ["JWT_SECRET"],
        jwt_ttl_seconds=int(os.environ.get("JWT_TTL_SECONDS", "900")),
        secret_pepper=os.environ["SECRET_PEPPER"],
        environment=os.environ.get("APP_ENV", "dev"),
    )
