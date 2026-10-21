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
class HashParams:
    algorithm: str
    iterations: int


@lru_cache
def hash_params() -> HashParams:
    return HashParams(
        algorithm=os.environ.get("HASH_ALGORITHM", "sha256"),
        iterations=int(os.environ.get("HASH_ITERATIONS", "600000")),
    )
