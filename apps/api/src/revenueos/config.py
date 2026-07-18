from functools import lru_cache
from typing import Literal

from pydantic import AliasChoices, Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

Environment = Literal["development", "test", "production"]
AuthMode = Literal["mock", "clerk"]
AIProviderName = Literal["mock", "openai"]


class Settings(BaseSettings):
    """Validated environment-backed application configuration."""

    model_config = SettingsConfigDict(
        env_prefix="API_",
        env_file=(".env", "apps/api/.env"),
        extra="ignore",
        case_sensitive=False,
        populate_by_name=True,
    )

    environment: Environment = "development"
    auth_mode: AuthMode = "mock"
    mock_auth_enabled: bool = True
    log_level: str = Field(default="INFO", pattern="^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$")
    cors_origins: str = Field(
        default="http://localhost:3000",
        validation_alias=AliasChoices("API_CORS_ORIGINS", "CORS_ORIGINS"),
    )
    database_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices("API_DATABASE_URL", "DATABASE_URL"),
    )
    clerk_jwks_url: str | None = None
    clerk_issuer: str | None = None
    clerk_audience: str | None = None
    worker_poll_interval_seconds: float = Field(default=1.0, gt=0, le=60)
    worker_lease_duration_seconds: int = Field(default=60, ge=10, le=3600)
    worker_heartbeat_interval_seconds: int = Field(default=20, ge=1, le=1200)
    worker_base_retry_delay_seconds: int = Field(default=5, ge=1, le=3600)
    worker_max_retry_delay_seconds: int = Field(default=300, ge=1, le=86400)
    worker_default_max_attempts: int = Field(default=3, ge=1, le=20)
    ai_provider_name: AIProviderName = Field(
        default="mock",
        validation_alias=AliasChoices("AI_PROVIDER", "API_AI_PROVIDER_NAME"),
    )
    ai_provider_model_identifier: str = Field(
        default="mock-infrastructure-v1",
        min_length=1,
        max_length=200,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:/-]*$",
    )
    ai_provider_timeout_seconds: float = Field(default=10.0, gt=0, le=300)
    openai_api_key: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("OPENAI_API_KEY", "API_OPENAI_API_KEY"),
    )
    openai_model: str | None = Field(
        default=None,
        min_length=1,
        max_length=200,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:/-]*$",
        validation_alias=AliasChoices("OPENAI_MODEL", "API_OPENAI_MODEL"),
    )
    openai_timeout_seconds: float = Field(
        default=30.0,
        gt=0,
        le=300,
        validation_alias=AliasChoices(
            "OPENAI_TIMEOUT_SECONDS",
            "API_OPENAI_TIMEOUT_SECONDS",
        ),
    )
    openai_max_output_tokens: int = Field(
        default=4_096,
        ge=256,
        le=32_768,
        validation_alias=AliasChoices(
            "OPENAI_MAX_OUTPUT_TOKENS",
            "API_OPENAI_MAX_OUTPUT_TOKENS",
        ),
    )
    ai_prompt_key: str = Field(
        default="infrastructure_test",
        min_length=1,
        max_length=100,
        pattern=r"^[a-z0-9][a-z0-9_]*$",
    )
    ai_structured_output_max_attempts: int = Field(default=3, ge=1, le=5)

    @field_validator(
        "database_url",
        "clerk_jwks_url",
        "clerk_issuer",
        "clerk_audience",
        "openai_api_key",
        "openai_model",
        mode="before",
    )
    @classmethod
    def normalise_optional_string(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        if isinstance(value, str):
            return value.strip()
        return value

    @model_validator(mode="after")
    def validate_security_configuration(self) -> "Settings":
        if self.auth_mode == "mock" and not self.mock_auth_enabled:
            raise ValueError("Mock authentication mode requires API_MOCK_AUTH_ENABLED=true.")
        if self.environment == "production":
            if self.auth_mode != "clerk" or self.mock_auth_enabled:
                raise ValueError("Production requires Clerk mode with mock authentication disabled.")
            if not self.clerk_configuration_complete:
                raise ValueError("Production requires complete Clerk verification configuration.")
            if "*" in self.cors_origin_list:
                raise ValueError("Production CORS origins must be explicit.")
        if self.worker_heartbeat_interval_seconds >= self.worker_lease_duration_seconds:
            raise ValueError("Worker heartbeat interval must be shorter than the lease duration.")
        if self.worker_base_retry_delay_seconds > self.worker_max_retry_delay_seconds:
            raise ValueError("Worker base retry delay cannot exceed the maximum retry delay.")
        if self.ai_provider_name == "openai":
            if self.openai_api_key is None:
                raise ValueError("OPENAI_API_KEY is required when AI_PROVIDER=openai.")
            api_key = self.openai_api_key.get_secret_value()
            if len(api_key) < 8 or len(api_key) > 512 or any(character.isspace() for character in api_key):
                raise ValueError("OPENAI_API_KEY is malformed.")
            if self.openai_model is None:
                raise ValueError("OPENAI_MODEL is required when AI_PROVIDER=openai.")
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def clerk_configuration_complete(self) -> bool:
        return all((self.clerk_jwks_url, self.clerk_issuer, self.clerk_audience))

    @property
    def selected_ai_model_identifier(self) -> str:
        if self.ai_provider_name == "openai":
            assert self.openai_model is not None
            return self.openai_model
        return self.ai_provider_model_identifier

    @property
    def selected_ai_timeout_seconds(self) -> float:
        if self.ai_provider_name == "openai":
            return self.openai_timeout_seconds
        return self.ai_provider_timeout_seconds

    def safe_ai_configuration(self) -> dict[str, object]:
        """Return metadata-only provider configuration suitable for diagnostics."""

        return {
            "provider": self.ai_provider_name,
            "model": self.selected_ai_model_identifier,
            "timeout_seconds": self.selected_ai_timeout_seconds,
            "max_output_tokens": (self.openai_max_output_tokens if self.ai_provider_name == "openai" else None),
            "external_content_transmission": self.ai_provider_name == "openai",
        }


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
