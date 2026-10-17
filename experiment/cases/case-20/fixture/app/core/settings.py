import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    database_url: str = os.environ.get("DATABASE_URL", "postgresql+asyncpg://localhost/pacer")
    push_gateway_url: str = os.environ.get("PUSH_GATEWAY_URL", "https://push.internal/v1/send")
    push_gateway_token: str = os.environ.get("PUSH_GATEWAY_TOKEN", "")
    idempotency_ttl_hours: int = int(os.environ.get("IDEMPOTENCY_TTL_HOURS", "24"))


settings = Settings()
