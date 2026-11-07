from functools import lru_cache

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="MOVEMENT_", env_file=".env", extra="ignore", hide_input_in_errors=True
    )

    database_url: SecretStr
    database_schema: str | None = Field(default=None, pattern=r"^[a-z_][a-z0-9_]{0,62}$")
    session_secret: SecretStr
    operator_username: str = "admin"
    operator_password_hash: SecretStr
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])
    session_ttl_seconds: int = Field(default=3600, ge=60, le=86400)
    stale_after_seconds: int = Field(default=90, ge=15, le=86400)
    retention_enabled: bool = True
    retention_interval_seconds: int = Field(default=3600, ge=60, le=86400)
    energy_per_send_j: float = Field(default=0.32, gt=0, le=100)
    sampling_budget_ratio: float = Field(default=0.5, gt=0, le=1)
    openweather_api_key: SecretStr | None = None

    @field_validator("database_url")
    @classmethod
    def postgres_only(cls, value: SecretStr) -> SecretStr:
        if not value.get_secret_value().startswith("postgresql+psycopg://"):
            raise ValueError("Use uma URL postgresql+psycopg://")
        return value

    @field_validator("session_secret")
    @classmethod
    def strong_secret(cls, value: SecretStr) -> SecretStr:
        raw = value.get_secret_value()
        if len(raw) < 32 or raw.startswith("GERE_"):
            raise ValueError("Gere um segredo aleatório de pelo menos 32 caracteres")
        return value

    @field_validator("operator_password_hash")
    @classmethod
    def password_hash_format(cls, value: SecretStr) -> SecretStr:
        if not value.get_secret_value().startswith("scrypt$"):
            raise ValueError("Gere o hash com movement password-hash")
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
