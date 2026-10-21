import os
from dataclasses import dataclass
from functools import lru_cache


@dataclass(frozen=True)
class Settings:
    database_url: str
    jwt_secret: str
    jwt_ttl_seconds: int
    secret_pepper: str
    cache_ttl_seconds: int
    log_level: str
    environment: str


@lru_cache
def get_settings() -> Settings:
    return Settings(
        database_url=os.environ["DATABASE_URL"],
        jwt_secret=os.environ["JWT_SECRET"],
        jwt_ttl_seconds=int(os.environ.get("JWT_TTL_SECONDS", "900")),
        secret_pepper=os.environ["SECRET_PEPPER"],
        cache_ttl_seconds=int(os.environ.get("CACHE_TTL_SECONDS", "300")),
        log_level=os.environ.get("LOG_LEVEL", "INFO"),
        environment=os.environ.get("APP_ENV", "dev"),
    )


@dataclass(frozen=True)
class Argon2Params:
    time_cost: int
    memory_kib: int
    parallelism: int


@lru_cache
def argon2_params() -> Argon2Params:
    return Argon2Params(
        time_cost=int(os.environ.get("ARGON2_TIME_COST", "3")),
        memory_kib=int(os.environ.get("ARGON2_MEMORY_KIB", "65536")),
        parallelism=int(os.environ.get("ARGON2_PARALLELISM", "2")),
    )
