import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    database_url: str = os.environ.get("DATABASE_URL", "postgresql+asyncpg://localhost/orders")
    fraud_base_url: str = os.environ.get("FRAUD_BASE_URL", "https://fraud.internal")
    payments_base_url: str = os.environ.get("PAYMENTS_BASE_URL", "https://api.paycore.example")
    payments_api_key: str = os.environ.get("PAYMENTS_API_KEY", "")


settings = Settings()
