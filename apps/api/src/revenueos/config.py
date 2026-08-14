from functools import lru_cache
from typing import Literal

from pydantic import AliasChoices, Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

Environment = Literal["development", "test", "production"]
AuthMode = Literal["mock", "clerk"]
AIProviderName = Literal["mock", "openai"]
TranscriptionProviderName = Literal["mock", "openai"]
VisualProviderName = Literal["mock", "openai"]
VisualStorageBackend = Literal["local", "s3_compatible"]


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
    clerk_jwks_timeout_seconds: float = Field(default=5.0, gt=0, le=15)
    clerk_jwt_leeway_seconds: int = Field(default=30, ge=0, le=120)
    private_beta_data_notice_version: int = Field(default=1, ge=1)
    private_beta_default_retention_days: int = Field(default=90)
    private_beta_max_generations_per_day: int = Field(default=100, ge=1, le=10_000)
    private_beta_max_openai_requests_per_day: int = Field(default=150, ge=1, le=10_000)
    private_beta_max_transcript_characters: int = Field(default=200_000, ge=1_000, le=1_000_000)
    private_beta_max_debrief_sessions_per_day: int = Field(default=25, ge=1, le=500)
    private_beta_debrief_question_cap: int = Field(default=6, ge=1, le=10)
    private_beta_max_debrief_audio_seconds: int = Field(default=120, ge=15, le=180)
    private_beta_max_debrief_audio_bytes: int = Field(default=8_000_000, ge=100_000, le=12_000_000)
    private_beta_max_visuals_per_interaction: int = Field(default=20, ge=1, le=100)
    private_beta_max_visual_bytes: int = Field(default=10_000_000, ge=100_000, le=25_000_000)
    private_beta_max_visual_bytes_per_interaction: int = Field(
        default=80_000_000,
        ge=1_000_000,
        le=500_000_000,
    )
    private_beta_max_visual_dimension: int = Field(default=12_000, ge=256, le=30_000)
    private_beta_max_visual_pixels: int = Field(default=40_000_000, ge=65_536, le=100_000_000)
    private_beta_max_visual_ai_requests_per_day: int = Field(default=50, ge=1, le=5_000)
    private_beta_visual_processing_retries: int = Field(default=3, ge=1, le=5)
    private_beta_feedback_per_user_per_day: int = Field(default=20, ge=1, le=1_000)
    private_beta_retention_batch_size: int = Field(default=100, ge=1, le=1_000)
    private_beta_export_directory: str = Field(default="/tmp/revenueos-private-beta-exports", min_length=1)
    private_beta_export_visual_images_enabled: bool = False
    feature_openai_provider_enabled: bool = False
    feature_revenue_brain_enabled: bool = True
    feature_opportunity_workspace_enabled: bool = True
    feature_ai_companion_enabled: bool = True
    feature_ai_debrief_enabled: bool = True
    feature_voice_journal_enabled: bool = True
    feature_visual_evidence_enabled: bool = True
    feature_presentation_mode_enabled: bool = True
    feature_data_export_enabled: bool = True
    feature_organisation_deletion_enabled: bool = False
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
    transcription_provider_name: TranscriptionProviderName = "mock"
    transcription_model_identifier: str = Field(
        default="gpt-4o-mini-transcribe",
        min_length=1,
        max_length=200,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:/-]*$",
    )
    transcription_timeout_seconds: float = Field(default=30.0, gt=0, le=120)
    visual_provider_name: VisualProviderName = "mock"
    visual_provider_model_identifier: str = Field(
        default="mock-visual-evidence-v1",
        min_length=1,
        max_length=200,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:/-]*$",
    )
    visual_provider_timeout_seconds: float = Field(default=30.0, gt=0, le=120)
    visual_storage_backend: VisualStorageBackend = "local"
    visual_storage_directory: str = Field(default="/tmp/revenueos-visual-evidence", min_length=1)
    visual_storage_signing_secret: SecretStr = Field(
        default=SecretStr("local-development-visual-signing-key"),
        min_length=24,
    )
    visual_signed_url_ttl_seconds: int = Field(default=300, ge=30, le=900)
    visual_s3_endpoint: str | None = None
    visual_s3_bucket: str | None = None
    visual_s3_region: str | None = None
    visual_s3_access_key_id: SecretStr | None = None
    visual_s3_secret_access_key: SecretStr | None = None

    @field_validator(
        "database_url",
        "clerk_jwks_url",
        "clerk_issuer",
        "clerk_audience",
        "openai_api_key",
        "openai_model",
        "visual_s3_endpoint",
        "visual_s3_bucket",
        "visual_s3_region",
        "visual_s3_access_key_id",
        "visual_s3_secret_access_key",
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
            if self.database_url is None or not self.database_url.startswith(("postgresql", "postgres")):
                raise ValueError("Production requires PostgreSQL persistence.")
        if self.worker_heartbeat_interval_seconds >= self.worker_lease_duration_seconds:
            raise ValueError("Worker heartbeat interval must be shorter than the lease duration.")
        if self.worker_base_retry_delay_seconds > self.worker_max_retry_delay_seconds:
            raise ValueError("Worker base retry delay cannot exceed the maximum retry delay.")
        if self.private_beta_default_retention_days not in {30, 90, 180}:
            raise ValueError("Private beta default retention must be 30, 90 or 180 days.")
        if (
            self.ai_provider_name == "openai"
            or self.transcription_provider_name == "openai"
            or self.visual_provider_name == "openai"
        ):
            if self.openai_api_key is None:
                raise ValueError("OPENAI_API_KEY is required when an OpenAI processing path is enabled.")
            api_key = self.openai_api_key.get_secret_value()
            if len(api_key) < 8 or len(api_key) > 512 or any(character.isspace() for character in api_key):
                raise ValueError("OPENAI_API_KEY is malformed.")
            if self.ai_provider_name == "openai" and self.openai_model is None:
                raise ValueError("OPENAI_MODEL is required when AI_PROVIDER=openai.")
            if not self.feature_openai_provider_enabled:
                raise ValueError("OpenAI requires the server-side beta feature flag.")
        if self.visual_provider_name == "openai":
            if self.visual_provider_model_identifier.startswith("mock-"):
                raise ValueError("OpenAI visual processing requires a non-mock VISUAL_PROVIDER_MODEL_IDENTIFIER.")
            if not self.feature_openai_provider_enabled:
                raise ValueError("OpenAI visual processing requires the server-side beta feature flag.")
        if self.visual_storage_backend == "s3_compatible" and not all(
            (
                self.visual_s3_endpoint,
                self.visual_s3_bucket,
                self.visual_s3_region,
                self.visual_s3_access_key_id,
                self.visual_s3_secret_access_key,
            )
        ):
            raise ValueError("S3-compatible visual storage requires endpoint, bucket, region and credentials.")
        if self.environment == "production" and self.feature_visual_evidence_enabled:
            if self.visual_storage_backend != "s3_compatible":
                raise ValueError("Production visual evidence requires private S3-compatible object storage.")
            if self.visual_storage_signing_secret.get_secret_value() == "local-development-visual-signing-key":
                raise ValueError("Production visual evidence requires a deployment-specific signing secret.")
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

    def safe_feature_flags(self) -> dict[str, bool]:
        """Return the complete, product-safe server-authoritative flag set."""

        return {
            "openaiProvider": self.feature_openai_provider_enabled,
            "revenueBrain": self.feature_revenue_brain_enabled,
            "opportunityWorkspace": self.feature_opportunity_workspace_enabled,
            "aiCompanion": self.feature_ai_companion_enabled,
            "aiDebrief": self.feature_ai_debrief_enabled,
            "voiceJournal": self.feature_voice_journal_enabled,
            "visualEvidence": self.feature_visual_evidence_enabled,
            "presentationMode": self.feature_presentation_mode_enabled,
            "dataExport": self.feature_data_export_enabled,
            "organisationDeletion": self.feature_organisation_deletion_enabled,
        }


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
