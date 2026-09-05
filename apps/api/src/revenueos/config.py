import base64
import binascii
from functools import lru_cache
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import AliasChoices, Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

Environment = Literal["development", "test", "production"]
AuthMode = Literal["mock", "clerk"]
AIProviderName = Literal["mock", "openai"]
TranscriptionProviderName = Literal["mock", "openai"]
VisualProviderName = Literal["mock", "openai"]
EvidenceExtractionProviderName = Literal["mock", "openai"]
ProspectResearchProviderName = Literal["mock"]
VisualStorageBackend = Literal["local", "s3_compatible"]
BillingProviderName = Literal["deterministic", "stripe"]


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
    identity_jit_provisioning_enabled: bool = True
    log_level: str = Field(default="INFO", pattern="^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$")
    cors_origins: str = Field(
        default="http://localhost:3000",
        validation_alias=AliasChoices("API_CORS_ORIGINS", "CORS_ORIGINS"),
    )
    allowed_hosts: str = "localhost,127.0.0.1,testserver"
    database_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices("API_DATABASE_URL", "DATABASE_URL"),
    )
    feature_billing_enabled: bool = False
    billing_provider_name: BillingProviderName = "deterministic"
    billing_mode: Literal["test"] = "test"
    billing_webhook_secret: SecretStr = Field(
        default=SecretStr("local-development-billing-webhook-key"),
        min_length=24,
    )
    billing_success_url: str = "http://localhost:3000/billing/success"
    billing_cancel_url: str = "http://localhost:3000/settings"
    billing_portal_return_url: str = "http://localhost:3000/settings"
    stripe_secret_key: SecretStr | None = None
    stripe_api_base_url: str = "https://api.stripe.com"
    stripe_api_version: Literal["2026-02-25.clover"] = "2026-02-25.clover"
    stripe_connect_timeout_seconds: float = Field(default=5.0, gt=0, le=30)
    stripe_read_timeout_seconds: float = Field(default=15.0, gt=0, le=60)
    stripe_webhook_tolerance_seconds: int = Field(default=300, ge=30, le=900)
    stripe_price_core_monthly: str | None = Field(default=None, min_length=7, max_length=255)
    stripe_price_core_annual: str | None = Field(default=None, min_length=7, max_length=255)
    stripe_price_growth_monthly: str | None = Field(default=None, min_length=7, max_length=255)
    stripe_price_growth_annual: str | None = Field(default=None, min_length=7, max_length=255)
    stripe_price_complete_monthly: str | None = Field(default=None, min_length=7, max_length=255)
    stripe_price_complete_annual: str | None = Field(default=None, min_length=7, max_length=255)
    clerk_jwks_url: str | None = None
    clerk_issuer: str | None = None
    clerk_audience: str | None = None
    clerk_jwks_timeout_seconds: float = Field(default=5.0, gt=0, le=15)
    clerk_jwt_leeway_seconds: int = Field(default=30, ge=0, le=120)
    private_beta_data_notice_version: int = Field(default=1, ge=1)
    private_beta_real_data_enabled: bool = False
    private_beta_external_ai_approved: bool = False
    private_beta_legal_approval_reference: str | None = Field(default=None, min_length=3, max_length=200)
    private_beta_support_email: str | None = Field(default=None, min_length=3, max_length=320)
    private_beta_backup_encryption_key: SecretStr | None = None
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
    private_beta_max_active_recordings: int = Field(default=5, ge=1, le=50)
    private_beta_max_recording_duration_seconds: int = Field(default=10_800, ge=60, le=14_400)
    private_beta_max_recording_bytes: int = Field(default=536_870_912, ge=1_000_000, le=2_147_483_648)
    private_beta_max_recording_chunk_bytes: int = Field(default=8_388_608, ge=64_000, le=25_000_000)
    private_beta_max_recording_chunks: int = Field(default=4_096, ge=1, le=10_000)
    private_beta_max_recording_bytes_per_day: int = Field(
        default=1_073_741_824,
        ge=1_000_000,
        le=10_737_418_240,
    )
    private_beta_max_transcription_minutes_per_day: int = Field(default=600, ge=1, le=10_000)
    private_beta_max_transcription_requests_per_day: int = Field(default=25, ge=1, le=1_000)
    private_beta_max_simultaneous_transcriptions: int = Field(default=2, ge=1, le=20)
    private_beta_transcription_retries: int = Field(default=3, ge=1, le=5)
    private_beta_max_online_meeting_transcript_bytes: int = Field(
        default=524_288,
        ge=10_000,
        le=2_000_000,
    )
    private_beta_max_document_bytes: int = Field(default=15_000_000, ge=10_000, le=50_000_000)
    private_beta_max_document_pages: int = Field(default=100, ge=1, le=500)
    private_beta_max_document_text_characters: int = Field(default=500_000, ge=1_000, le=2_000_000)
    private_beta_max_document_uploads_per_day: int = Field(default=25, ge=1, le=1_000)
    private_beta_max_document_bytes_per_organisation: int = Field(
        default=1_000_000_000,
        ge=1_000_000,
        le=20_000_000_000,
    )
    private_beta_max_pptx_bytes: int = Field(default=50_000_000, ge=100_000, le=100_000_000)
    private_beta_max_pptx_slides: int = Field(default=100, ge=1, le=200)
    private_beta_max_pptx_zip_entries: int = Field(default=2_000, ge=10, le=10_000)
    private_beta_max_pptx_expanded_bytes: int = Field(
        default=250_000_000,
        ge=1_000_000,
        le=1_000_000_000,
    )
    private_beta_max_pptx_media_assets: int = Field(default=500, ge=0, le=1_000)
    private_beta_max_pptx_media_bytes: int = Field(default=10_000_000, ge=1_000, le=50_000_000)
    private_beta_max_pptx_xml_bytes: int = Field(default=5_000_000, ge=10_000, le=25_000_000)
    private_beta_max_pptx_extracted_characters: int = Field(
        default=250_000,
        ge=1_000,
        le=1_000_000,
    )
    private_beta_max_create_templates: int = Field(default=20, ge=1, le=100)
    private_beta_max_create_template_versions: int = Field(default=20, ge=1, le=100)
    private_beta_max_create_presentations_per_user_per_day: int = Field(default=10, ge=1, le=100)
    private_beta_max_create_presentations_per_organisation_per_day: int = Field(
        default=50,
        ge=1,
        le=1_000,
    )
    private_beta_max_create_slides: int = Field(default=30, ge=1, le=30)
    private_beta_create_processing_retries: int = Field(default=3, ge=1, le=3)
    private_beta_max_email_analyses_per_day: int = Field(default=50, ge=1, le=2_000)
    private_beta_max_ask_questions_per_user_per_day: int = Field(default=75, ge=1, le=1_000)
    private_beta_max_ask_questions_per_organisation_per_day: int = Field(default=500, ge=1, le=10_000)
    private_beta_ask_max_sources: int = Field(default=12, ge=1, le=20)
    private_beta_ask_max_context_characters: int = Field(default=16_000, ge=1_000, le=50_000)
    private_beta_ask_max_portfolio_results: int = Field(default=10, ge=1, le=20)
    private_beta_max_prospect_research_per_user_per_day: int = Field(default=20, ge=1, le=500)
    private_beta_max_prospect_research_per_organisation_per_day: int = Field(default=100, ge=1, le=2_000)
    private_beta_max_concurrent_prospect_research: int = Field(default=5, ge=1, le=50)
    private_beta_prospect_fresh_days: int = Field(default=7, ge=1, le=90)
    private_beta_max_people_discoveries_per_user_per_day: int = Field(default=10, ge=1, le=100)
    private_beta_max_people_discoveries_per_organisation_per_day: int = Field(default=50, ge=1, le=500)
    private_beta_max_prospect_people_per_discovery: int = Field(default=10, ge=1, le=15)
    private_beta_max_target_markets_per_organisation: int = Field(default=10, ge=1, le=50)
    private_beta_max_discovery_runs_per_user_per_day: int = Field(default=5, ge=1, le=100)
    private_beta_max_discovery_runs_per_organisation_per_day: int = Field(default=25, ge=1, le=500)
    private_beta_max_candidates_per_discovery: int = Field(default=50, ge=1, le=50)
    private_beta_max_outreach_per_user_per_day: int = Field(default=25, ge=1, le=500)
    private_beta_max_outreach_per_organisation_per_day: int = Field(default=100, ge=1, le=2_000)
    private_beta_max_campaign_recipients: int = Field(default=50, ge=1, le=50)
    private_beta_max_campaign_steps: int = Field(default=4, ge=1, le=4)
    private_beta_max_active_campaigns_per_user: int = Field(default=5, ge=1, le=20)
    private_beta_max_active_campaigns_per_organisation: int = Field(default=10, ge=1, le=50)
    private_beta_max_campaign_drafts_per_day: int = Field(default=100, ge=1, le=500)
    campaign_draft_preparation_hours: int = Field(default=24, ge=1, le=72)
    campaign_recipient_spacing_minutes: int = Field(default=5, ge=1, le=60)
    private_beta_max_active_events_per_organisation: int = Field(default=50, ge=1, le=100)
    private_beta_max_event_attendees: int = Field(default=500, ge=1, le=1_000)
    private_beta_max_event_imports_per_day: int = Field(default=5, ge=1, le=20)
    private_beta_max_action_generations_per_day: int = Field(default=100, ge=1, le=5_000)
    private_beta_max_email_executions_per_day: int = Field(default=50, ge=1, le=5_000)
    private_beta_max_calendar_executions_per_day: int = Field(default=25, ge=1, le=2_000)
    private_beta_max_crm_executions_per_day: int = Field(default=100, ge=1, le=10_000)
    private_beta_max_task_executions_per_day: int = Field(default=100, ge=1, le=10_000)
    private_beta_max_concurrent_executions: int = Field(default=5, ge=1, le=100)
    execution_preview_ttl_seconds: int = Field(default=600, ge=60, le=3_600)
    private_beta_live_processing_interval_seconds: int = Field(default=15, ge=5, le=60)
    private_beta_live_min_new_segments: int = Field(default=2, ge=1, le=10)
    private_beta_live_min_new_characters: int = Field(default=160, ge=40, le=2_000)
    private_beta_live_window_segments: int = Field(default=12, ge=4, le=30)
    private_beta_live_window_characters: int = Field(default=8_000, ge=1_000, le=20_000)
    private_beta_live_window_overlap_segments: int = Field(default=2, ge=0, le=5)
    private_beta_max_live_requests_per_minute: int = Field(default=4, ge=1, le=12)
    private_beta_max_live_requests_per_interaction: int = Field(default=120, ge=1, le=500)
    private_beta_max_live_characters_per_interaction: int = Field(default=200_000, ge=1_000, le=1_000_000)
    private_beta_max_concurrent_live_interactions: int = Field(default=3, ge=1, le=20)
    private_beta_max_live_provider_calls_per_day: int = Field(default=200, ge=1, le=5_000)
    private_beta_live_retention_days: int = Field(default=30, ge=1, le=90)
    private_beta_document_processing_retries: int = Field(default=3, ge=1, le=5)
    private_beta_email_processing_retries: int = Field(default=3, ge=1, le=5)
    private_beta_recording_session_expiry_hours: int = Field(default=24, ge=1, le=168)
    private_beta_raw_recording_retention_days: int = Field(default=7, ge=1, le=30)
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
    feature_recording_capture_enabled: bool = False
    feature_transcription_enabled: bool = False
    feature_auto_generate_intelligence_after_transcription: bool = False
    feature_online_meeting_capture_enabled: bool = True
    feature_online_meeting_import_enabled: bool = True
    feature_online_meeting_native_integration_enabled: bool = False
    feature_online_meeting_auto_ingest_enabled: bool = False
    feature_document_evidence_enabled: bool = True
    feature_email_evidence_enabled: bool = True
    feature_sales_methodology_enabled: bool = True
    feature_ask_revenueos_enabled: bool = True
    feature_live_interaction_intelligence_enabled: bool = False
    feature_live_interaction_external_ai_enabled: bool = False
    feature_action_layer_enabled: bool = True
    feature_action_manual_completion_enabled: bool = True
    feature_integrations_enabled: bool = False
    feature_action_execution_enabled: bool = False
    feature_mock_connectors_enabled: bool = False
    feature_hubspot_crm_enabled: bool = False
    feature_native_crm_enabled: bool = True
    feature_native_pipeline_enabled: bool = True
    feature_sales_analytics_enabled: bool = True
    feature_sales_targets_enabled: bool = True
    feature_sales_forecasting_enabled: bool = True
    feature_manager_intelligence_enabled: bool = True
    feature_data_export_enabled: bool = True
    feature_organisation_deletion_enabled: bool = False
    feature_prospect_enabled: bool = True
    feature_engage_enabled: bool = True
    feature_engage_campaigns_enabled: bool = True
    feature_engage_events_enabled: bool = False
    feature_create_enabled: bool = True
    outreach_suppression_hmac_key: SecretStr = Field(
        default=SecretStr("local-development-outreach-suppression-key"),
        min_length=24,
    )
    prospect_research_provider_name: ProspectResearchProviderName = "mock"
    worker_poll_interval_seconds: float = Field(default=1.0, gt=0, le=60)
    worker_lease_duration_seconds: int = Field(default=60, ge=10, le=3600)
    worker_heartbeat_interval_seconds: int = Field(default=20, ge=1, le=1200)
    worker_base_retry_delay_seconds: int = Field(default=5, ge=1, le=3600)
    worker_max_retry_delay_seconds: int = Field(default=300, ge=1, le=86400)
    worker_default_max_attempts: int = Field(default=3, ge=1, le=20)
    hubspot_client_id: str | None = Field(default=None, min_length=8, max_length=255)
    hubspot_client_secret: SecretStr | None = None
    hubspot_oauth_redirect_uri: str | None = Field(default=None, max_length=2048)
    hubspot_authorisation_base_url: str = "https://app.hubspot.com/oauth/authorize"
    hubspot_api_base_url: str = "https://api.hubapi.com"
    hubspot_connect_timeout_seconds: float = Field(default=5.0, gt=0, le=30)
    hubspot_read_timeout_seconds: float = Field(default=10.0, gt=0, le=60)
    hubspot_write_timeout_seconds: float = Field(default=15.0, gt=0, le=60)
    hubspot_oauth_state_ttl_seconds: int = Field(default=600, ge=120, le=1800)
    connector_credential_master_key: SecretStr | None = None
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
    transcription_provider_name: TranscriptionProviderName = Field(
        default="mock",
        validation_alias=AliasChoices(
            "TRANSCRIPTION_PROVIDER",
            "API_TRANSCRIPTION_PROVIDER",
            "API_TRANSCRIPTION_PROVIDER_NAME",
        ),
    )
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
    evidence_extraction_provider_name: EvidenceExtractionProviderName = "mock"
    evidence_extraction_model_identifier: str = Field(
        default="mock-evidence-extraction-v1",
        min_length=1,
        max_length=200,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:/-]*$",
    )
    evidence_extraction_timeout_seconds: float = Field(default=30.0, gt=0, le=120)
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
        "private_beta_legal_approval_reference",
        "private_beta_support_email",
        "private_beta_backup_encryption_key",
        "openai_api_key",
        "openai_model",
        "visual_s3_endpoint",
        "visual_s3_bucket",
        "visual_s3_region",
        "visual_s3_access_key_id",
        "visual_s3_secret_access_key",
        "stripe_secret_key",
        "stripe_price_core_monthly",
        "stripe_price_core_annual",
        "stripe_price_growth_monthly",
        "stripe_price_growth_annual",
        "stripe_price_complete_monthly",
        "stripe_price_complete_annual",
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
            if self.database_url is None or not self.database_url.startswith(("postgresql", "postgres")):
                raise ValueError("Production requires PostgreSQL persistence.")
            if "*" in self.cors_origin_list:
                raise ValueError("Production CORS origins must be explicit.")
            if not self.cors_origin_list or any(
                not self._is_public_https_origin(value) for value in self.cors_origin_list
            ):
                raise ValueError("Production CORS origins must use explicit public HTTPS origins.")
            if self.feature_mock_connectors_enabled:
                raise ValueError("Mock connectors are prohibited in production.")
            if (
                self.feature_engage_enabled
                and self.outreach_suppression_hmac_key.get_secret_value()
                == "local-development-outreach-suppression-key"
            ):
                raise ValueError("Production Engage requires a deployment-managed suppression HMAC key.")
            if self.log_level == "DEBUG":
                raise ValueError("Production log level must not be DEBUG.")
            if self.identity_jit_provisioning_enabled:
                raise ValueError("Production identity must use deliberate operator provisioning.")
            if (
                not self.allowed_host_list
                or "*" in self.allowed_host_list
                or any(
                    host in {"localhost", "127.0.0.1", "::1"} or host.endswith(".localhost")
                    for host in self.allowed_host_list
                )
            ):
                raise ValueError("Production allowed hosts must be explicit.")
            if self.feature_billing_enabled or self.billing_provider_name == "stripe":
                raise ValueError("Live billing is not authorised; billing providers are test-mode only.")
            if self.stripe_secret_key is not None:
                raise ValueError("Stripe credentials are prohibited in production until live billing is authorised.")
        if self.stripe_secret_key is not None:
            stripe_key = self.stripe_secret_key.get_secret_value()
            if stripe_key.startswith("sk_live_"):
                raise ValueError("Live Stripe credentials are prohibited.")
            if not stripe_key.startswith("sk_test_"):
                raise ValueError("Stripe test mode requires an sk_test_ secret key.")
        if self.feature_billing_enabled:
            if not self._is_safe_billing_return_url(self.billing_success_url):
                raise ValueError("Billing success URL must use HTTPS or an exact localhost HTTP origin.")
            if not self._is_safe_billing_return_url(self.billing_cancel_url):
                raise ValueError("Billing cancel URL must use HTTPS or an exact localhost HTTP origin.")
            if not self._is_safe_billing_return_url(self.billing_portal_return_url):
                raise ValueError("Billing portal return URL must use HTTPS or an exact localhost HTTP origin.")
            if self.billing_provider_name == "stripe":
                if self.stripe_secret_key is None:
                    raise ValueError("Stripe test billing requires API_STRIPE_SECRET_KEY.")
                price_ids = self.stripe_price_identifiers
                if any(value is None or not value.startswith("price_") for value in price_ids.values()):
                    raise ValueError("Stripe test billing requires all six price_ identifiers.")
                if self.stripe_api_base_url != "https://api.stripe.com":
                    raise ValueError("Stripe billing must use the official HTTPS API endpoint.")
        if self.private_beta_real_data_enabled:
            if self.environment != "production":
                raise ValueError("Real-data private beta mode is permitted only in production.")
            if self.private_beta_legal_approval_reference is None or self.private_beta_support_email is None:
                raise ValueError("Real-data private beta mode requires legal approval and support references.")
            if self.private_beta_backup_encryption_key is None:
                raise ValueError("Real-data private beta mode requires a backup encryption key.")
            try:
                backup_key = base64.b64decode(self.private_beta_backup_encryption_key.get_secret_value(), validate=True)
            except (binascii.Error, ValueError) as exc:
                raise ValueError("Backup encryption key must be valid base64.") from exc
            if len(backup_key) != 32:
                raise ValueError("Backup encryption key must decode to exactly 32 bytes.")
            if self.feature_data_export_enabled:
                export_path = Path(self.private_beta_export_directory).expanduser()
                if not export_path.is_absolute() or export_path == Path("/tmp") or Path("/tmp") in export_path.parents:
                    raise ValueError("Real-data exports require an explicit durable private directory outside /tmp.")
            external_ai_selected = any(
                provider == "openai"
                for provider in (
                    self.ai_provider_name,
                    self.transcription_provider_name,
                    self.visual_provider_name,
                    self.evidence_extraction_provider_name,
                )
            )
            if external_ai_selected and not self.private_beta_external_ai_approved:
                raise ValueError("External AI processing requires an explicit real-data approval.")
            if not external_ai_selected and self._mock_customer_content_features_enabled:
                raise ValueError(
                    "Real-data mode cannot expose mock intelligence over customer content; disable the listed "
                    "content-processing features or configure an approved external provider."
                )
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
            or self.evidence_extraction_provider_name == "openai"
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
        if self.evidence_extraction_provider_name == "openai":
            if self.evidence_extraction_model_identifier.startswith("mock-"):
                raise ValueError("OpenAI evidence extraction requires a non-mock model identifier.")
            if not self.feature_openai_provider_enabled:
                raise ValueError("OpenAI evidence extraction requires the server-side beta feature flag.")
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
        if self.environment == "production" and (
            self.feature_visual_evidence_enabled
            or self.feature_recording_capture_enabled
            or self.feature_online_meeting_capture_enabled
            or self.feature_document_evidence_enabled
            or self.feature_create_enabled
        ):
            if self.visual_storage_backend != "s3_compatible":
                raise ValueError("Production binary evidence requires private S3-compatible object storage.")
            if self.visual_storage_signing_secret.get_secret_value() == "local-development-visual-signing-key":
                raise ValueError("Production binary evidence requires a deployment-specific signing secret.")
        if self.feature_auto_generate_intelligence_after_transcription and not self.feature_transcription_enabled:
            raise ValueError("Automatic intelligence after transcription requires transcription to be enabled.")
        if self.feature_online_meeting_import_enabled and not self.feature_online_meeting_capture_enabled:
            raise ValueError("Online-meeting import requires online-meeting capture to be enabled.")
        if self.feature_online_meeting_native_integration_enabled and not self.feature_online_meeting_capture_enabled:
            raise ValueError("Online-meeting native integration requires online-meeting capture to be enabled.")
        if (
            self.feature_online_meeting_auto_ingest_enabled
            and not self.feature_online_meeting_native_integration_enabled
        ):
            raise ValueError("Online-meeting auto-ingest requires a native integration to be enabled.")
        if self.private_beta_live_window_overlap_segments >= self.private_beta_live_window_segments:
            raise ValueError("Live transcript overlap must be smaller than the processing window.")
        if self.feature_live_interaction_external_ai_enabled and not (
            self.feature_live_interaction_intelligence_enabled and self.feature_openai_provider_enabled
        ):
            raise ValueError("External live intelligence requires both live intelligence and OpenAI feature flags.")
        if self.feature_action_execution_enabled and not (
            self.feature_integrations_enabled and self.feature_action_layer_enabled
        ):
            raise ValueError("Action execution requires the Integrations and Action Layer feature flags.")
        if self.feature_mock_connectors_enabled and not self.feature_integrations_enabled:
            raise ValueError("Mock connectors require the Integrations feature flag.")
        if self.feature_hubspot_crm_enabled:
            if not (self.feature_integrations_enabled and self.feature_action_execution_enabled):
                raise ValueError("HubSpot CRM requires Integrations and Action Execution feature flags.")
            if not all(
                (
                    self.hubspot_client_id,
                    self.hubspot_client_secret,
                    self.hubspot_oauth_redirect_uri,
                    self.connector_credential_master_key,
                )
            ):
                raise ValueError(
                    "HubSpot CRM requires client credentials, an exact redirect URI and an encryption master key."
                )
            assert self.hubspot_oauth_redirect_uri is not None
            if self.environment == "production" and not self.hubspot_oauth_redirect_uri.startswith("https://"):
                raise ValueError("Production HubSpot OAuth requires an HTTPS redirect URI.")
            if self.hubspot_api_base_url != "https://api.hubapi.com":
                raise ValueError("HubSpot API host must use the official HTTPS endpoint.")
            if self.hubspot_authorisation_base_url != "https://app.hubspot.com/oauth/authorize":
                raise ValueError("HubSpot authorisation must use the official HTTPS endpoint.")
            assert self.connector_credential_master_key is not None
            from revenueos.credential_store import EncryptedDatabaseCredentialStore

            EncryptedDatabaseCredentialStore.decode_master_key(self.connector_credential_master_key.get_secret_value())
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def allowed_host_list(self) -> list[str]:
        return [host.strip().lower() for host in self.allowed_hosts.split(",") if host.strip()]

    @staticmethod
    def _is_public_https_origin(value: str) -> bool:
        parsed = urlsplit(value)
        hostname = (parsed.hostname or "").casefold()
        return (
            parsed.scheme == "https"
            and bool(hostname)
            and parsed.path in {"", "/"}
            and not parsed.query
            and not parsed.fragment
            and hostname not in {"localhost", "127.0.0.1", "::1"}
            and not hostname.endswith(".localhost")
        )

    @staticmethod
    def _is_safe_billing_return_url(value: str) -> bool:
        parsed = urlsplit(value)
        hostname = (parsed.hostname or "").casefold()
        if parsed.username or parsed.password or parsed.fragment or not hostname:
            return False
        if parsed.scheme == "https":
            return True
        return parsed.scheme == "http" and hostname in {"localhost", "127.0.0.1", "::1"}

    @property
    def stripe_price_identifiers(self) -> dict[tuple[str, str], str | None]:
        return {
            ("core", "monthly"): self.stripe_price_core_monthly,
            ("core", "annual"): self.stripe_price_core_annual,
            ("growth", "monthly"): self.stripe_price_growth_monthly,
            ("growth", "annual"): self.stripe_price_growth_annual,
            ("complete", "monthly"): self.stripe_price_complete_monthly,
            ("complete", "annual"): self.stripe_price_complete_annual,
        }

    @property
    def _mock_customer_content_features_enabled(self) -> bool:
        return any(
            (
                self.feature_revenue_brain_enabled,
                self.feature_ai_companion_enabled,
                self.feature_ai_debrief_enabled,
                self.feature_voice_journal_enabled,
                self.feature_visual_evidence_enabled,
                self.feature_recording_capture_enabled,
                self.feature_transcription_enabled,
                self.feature_online_meeting_capture_enabled,
                self.feature_document_evidence_enabled,
                self.feature_email_evidence_enabled,
                self.feature_ask_revenueos_enabled,
                self.feature_live_interaction_intelligence_enabled,
                self.feature_prospect_enabled,
                self.feature_engage_enabled,
                self.feature_engage_campaigns_enabled,
                self.feature_engage_events_enabled,
                self.feature_create_enabled,
            )
        )

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
            "recordingCapture": self.feature_recording_capture_enabled,
            "transcription": self.feature_transcription_enabled,
            "autoGenerateIntelligenceAfterTranscription": (self.feature_auto_generate_intelligence_after_transcription),
            "onlineMeetingCapture": self.feature_online_meeting_capture_enabled,
            "onlineMeetingImport": self.feature_online_meeting_import_enabled,
            "onlineMeetingNativeIntegration": self.feature_online_meeting_native_integration_enabled,
            "onlineMeetingAutoIngest": self.feature_online_meeting_auto_ingest_enabled,
            "documentEvidence": self.feature_document_evidence_enabled,
            "emailEvidence": self.feature_email_evidence_enabled,
            "salesMethodology": self.feature_sales_methodology_enabled,
            "askRevenueOS": self.feature_ask_revenueos_enabled,
            "liveInteractionIntelligence": self.feature_live_interaction_intelligence_enabled,
            "liveInteractionExternalAi": self.feature_live_interaction_external_ai_enabled,
            "actionLayer": self.feature_action_layer_enabled,
            "actionManualCompletion": self.feature_action_manual_completion_enabled,
            "integrations": self.feature_integrations_enabled,
            "actionExecution": self.feature_action_execution_enabled,
            "mockConnectors": self.feature_mock_connectors_enabled,
            "hubspotCrm": self.feature_hubspot_crm_enabled,
            "nativeCrm": self.feature_native_crm_enabled,
            "nativePipeline": self.feature_native_pipeline_enabled,
            "salesAnalytics": self.feature_sales_analytics_enabled,
            "salesTargets": self.feature_sales_targets_enabled and self.feature_sales_analytics_enabled,
            "salesForecasting": (
                self.feature_sales_forecasting_enabled
                and self.feature_sales_targets_enabled
                and self.feature_sales_analytics_enabled
            ),
            "managerIntelligence": (
                self.feature_manager_intelligence_enabled
                and self.feature_sales_forecasting_enabled
                and self.feature_sales_targets_enabled
                and self.feature_sales_analytics_enabled
                and self.feature_sales_methodology_enabled
            ),
            "dataExport": self.feature_data_export_enabled,
            "organisationDeletion": self.feature_organisation_deletion_enabled,
            "prospect": self.feature_prospect_enabled,
            "engage": self.feature_engage_enabled,
            "engageCampaigns": self.feature_engage_campaigns_enabled,
            "engageEvents": self.feature_engage_events_enabled,
            "create": self.feature_create_enabled,
        }


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
