from __future__ import annotations

import json
import re
from pathlib import Path
from typing import cast

import yaml

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
APP_SPEC_PATH = REPOSITORY_ROOT / "infra/digitalocean/app.production.template.yaml"
PRODUCTION_ENV_PATH = REPOSITORY_ROOT / "infra/environments/production.env.example"
WEB_DOCKERFILE_PATH = REPOSITORY_ROOT / "infra/docker/web.Dockerfile"
BACKUP_LIFECYCLE_PATH = REPOSITORY_ROOT / "infra/aws/independent-backup-lifecycle.json"


def _app_spec() -> dict[str, object]:
    value = yaml.safe_load(APP_SPEC_PATH.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return cast(dict[str, object], value)


def _component_map(value: object) -> dict[str, dict[str, object]]:
    assert isinstance(value, list)
    components: dict[str, dict[str, object]] = {}
    for untyped_component in value:
        assert isinstance(untyped_component, dict)
        component = cast(dict[str, object], untyped_component)
        name = component.get("name")
        assert isinstance(name, str)
        assert name not in components
        components[name] = component
    return components


def _component_environment(component: dict[str, object]) -> dict[str, dict[str, object]]:
    untyped_environment = component.get("envs")
    assert isinstance(untyped_environment, list)
    environment: dict[str, dict[str, object]] = {}
    for untyped_entry in untyped_environment:
        assert isinstance(untyped_entry, dict)
        entry = cast(dict[str, object], untyped_entry)
        key = entry.get("key")
        assert isinstance(key, str)
        assert key not in environment
        environment[key] = entry
    return environment


def _production_environment_contract() -> dict[str, str]:
    environment: dict[str, str] = {}
    for raw_line in PRODUCTION_ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        key, separator, value = line.partition("=")
        assert separator == "="
        assert re.fullmatch(r"[A-Z][A-Z0-9_]*", key)
        assert key not in environment, f"duplicate production environment key: {key}"
        environment[key] = value
    return environment


def test_digitalocean_topology_and_production_defaults_are_fail_closed() -> None:
    spec = _app_spec()
    assert spec["name"] == "oryntela-production"
    assert spec["region"] == "syd"
    assert spec["domains"] == [
        {
            "domain": "oryntela.com.au",
            "type": "PRIMARY",
            "minimum_tls_version": "1.2",
        },
        {
            "domain": "www.oryntela.com.au",
            "type": "ALIAS",
            "minimum_tls_version": "1.2",
        },
        {
            "domain": "api.oryntela.com.au",
            "type": "ALIAS",
            "minimum_tls_version": "1.2",
        },
    ]
    assert all("zone" not in domain for domain in cast(list[dict[str, object]], spec["domains"]))
    services = _component_map(spec["services"])
    workers = _component_map(spec["workers"])
    jobs = _component_map(spec["jobs"])
    assert set(services) == {"web", "api"}
    assert set(workers) == {"worker"}
    assert set(jobs) == {"migrate", "daily-independent-backup"}

    all_components = [*services.values(), *workers.values(), *jobs.values()]
    for component in all_components:
        assert component["source_dir"] == "/"
        source = cast(dict[str, object], component["github"])
        assert source == {
            "repo": "KevinFinnerty2205/revenueos",
            "branch": "main",
            "deploy_on_push": False,
        }

    assert services["web"]["dockerfile_path"] == "infra/docker/web.Dockerfile"
    assert services["api"]["dockerfile_path"] == "infra/docker/api.Dockerfile"
    assert services["web"]["http_port"] == 8080
    assert services["web"]["health_check"] == {
        "http_path": "/health/ready",
        "initial_delay_seconds": 20,
        "period_seconds": 15,
        "timeout_seconds": 5,
        "success_threshold": 1,
        "failure_threshold": 5,
    }
    assert services["web"]["liveness_health_check"]["http_path"] == "/"
    assert services["api"]["http_port"] == 8080
    assert services["api"]["health_check"] == {
        "http_path": "/health/ready",
        "initial_delay_seconds": 20,
        "period_seconds": 15,
        "timeout_seconds": 5,
        "success_threshold": 1,
        "failure_threshold": 5,
    }
    assert services["api"]["liveness_health_check"]["http_path"] == "/health/live"
    assert services["web"]["termination"] == {"drain_seconds": 15, "grace_period_seconds": 120}
    assert services["api"]["termination"] == {"drain_seconds": 15, "grace_period_seconds": 120}
    for component in (*services.values(), *workers.values()):
        assert component["instance_count"] == 1
        assert component["instance_size_slug"] == "apps-s-1vcpu-1gb-fixed"
    assert workers["worker"]["run_command"] == "revenueos-ai-worker"
    assert workers["worker"]["liveness_health_check"] == {
        "http_path": "/health",
        "port": 8081,
        "initial_delay_seconds": 30,
        "period_seconds": 30,
        "timeout_seconds": 5,
        "failure_threshold": 5,
    }
    assert workers["worker"]["termination"] == {"grace_period_seconds": 300}

    ingress = cast(dict[str, object], spec["ingress"])
    rules = cast(list[dict[str, object]], ingress["rules"])
    assert all(cast(dict[str, object], rule["component"])["name"] != "worker" for rule in rules)
    assert rules[0] == {
        "component": {"name": "api"},
        "match": {"authority": {"exact": "api.oryntela.com.au"}, "path": {"prefix": "/"}},
    }

    api_environment = _component_environment(services["api"])
    worker_environment = _component_environment(workers["worker"])
    assert api_environment == worker_environment
    required_inert_values = {
        "API_ENVIRONMENT": "production",
        "API_AUTH_MODE": "clerk",
        "API_MOCK_AUTH_ENABLED": "false",
        "API_IDENTITY_JIT_PROVISIONING_ENABLED": "false",
        "API_PRIVATE_BETA_REAL_DATA_ENABLED": "false",
        "API_PRIVATE_BETA_DEFAULT_RETENTION_DAYS": "90",
        "API_FEATURE_DATA_EXPORT_ENABLED": "false",
        "API_FEATURE_ORGANISATION_DELETION_ENABLED": "false",
        "API_PRIVATE_BETA_EXTERNAL_AI_APPROVED": "false",
        "API_FEATURE_OPENAI_PROVIDER_ENABLED": "false",
        "AI_PROVIDER": "mock",
        "API_FEATURE_BILLING_ENABLED": "false",
        "API_FEATURE_CREDITS_ENABLED": "false",
        "API_BILLING_PROVIDER_NAME": "deterministic",
        "API_BILLING_MODE": "test",
        "API_BILLING_TAX_TREATMENT": "unresolved",
        "API_BILLING_SUCCESS_URL": "https://oryntela.com.au/billing/success",
        "API_BILLING_CANCEL_URL": "https://oryntela.com.au/settings",
        "API_BILLING_PORTAL_RETURN_URL": "https://oryntela.com.au/settings",
        "API_STRIPE_API_VERSION": "2026-02-25.clover",
        "API_PROSPECT_RESEARCH_PROVIDER_NAME": "mock",
        "API_FEATURE_PROSPECT_EXTERNAL_PROVIDER_ENABLED": "false",
        "API_FEATURE_INTEGRATIONS_ENABLED": "false",
        "API_FEATURE_ACTION_EXECUTION_ENABLED": "false",
        "API_FEATURE_MOCK_CONNECTORS_ENABLED": "false",
        "API_FEATURE_MICROSOFT_365_ENABLED": "false",
        "API_FEATURE_GOOGLE_WORKSPACE_ENABLED": "false",
        "API_FEATURE_HUBSPOT_CRM_ENABLED": "false",
        "API_FEATURE_SALESFORCE_CRM_ENABLED": "false",
    }
    assert {key: api_environment[key].get("value") for key in required_inert_values} == required_inert_values
    assert api_environment["OPENAI_MODEL"]["value"] == "gpt-5.6-terra"
    assert api_environment["OPENAI_MAX_OUTPUT_TOKENS"]["value"] == "4096"
    assert {
        "OPENAI_API_KEY",
        "API_CONNECTOR_CREDENTIAL_MASTER_KEY",
        "API_MICROSOFT_CLIENT_SECRET",
        "API_GOOGLE_CLIENT_SECRET",
        "API_HUBSPOT_CLIENT_SECRET",
        "API_SALESFORCE_CLIENT_SECRET",
        "API_APOLLO_API_KEY",
        "API_STRIPE_SECRET_KEY",
    }.isdisjoint(api_environment)
    for entry in api_environment.values():
        if entry.get("type") == "SECRET":
            assert "value" not in entry


def test_migration_and_backup_jobs_have_separate_minimum_authority() -> None:
    jobs = _component_map(_app_spec()["jobs"])
    migration = jobs["migrate"]
    backup = jobs["daily-independent-backup"]
    assert migration["kind"] == "PRE_DEPLOY"
    assert migration["run_command"] == "alembic upgrade head"
    assert migration["instance_count"] == 1
    assert migration["instance_size_slug"] == "apps-s-1vcpu-0.5gb"
    assert set(_component_environment(migration)) == {
        "DATABASE_URL",
        "API_DATABASE_TLS_MODE",
        "API_DATABASE_CA_CERTIFICATE_BASE64",
    }
    assert backup["kind"] == "SCHEDULED"
    assert backup["run_command"] == "revenueos-backup create-remote"
    assert backup["instance_count"] == 1
    assert backup["instance_size_slug"] == "apps-s-1vcpu-1gb-fixed"
    assert backup["schedule"] == {
        "cron": "30 3 * * *",
        "time_zone": "Australia/Sydney",
    }
    backup_environment = _component_environment(backup)
    assert "DATABASE_URL" not in backup_environment
    assert "API_BACKUP_SOURCE_DATABASE_URL" in backup_environment
    assert "API_BACKUP_ENCRYPTION_KEY" in backup_environment
    assert "API_BACKUP_SOURCE_S3_SECRET_ACCESS_KEY" in backup_environment
    assert "API_BACKUP_DESTINATION_S3_SECRET_ACCESS_KEY" in backup_environment
    assert all(key.startswith("API_BACKUP_") for key in backup_environment)


def test_web_build_arguments_match_provider_build_time_contract() -> None:
    web = _component_map(_app_spec()["services"])["web"]
    environment = _component_environment(web)
    build_time_keys = {
        key for key, entry in environment.items() if entry.get("scope") in {"BUILD_TIME", "RUN_AND_BUILD_TIME"}
    }
    dockerfile_arguments = set(
        re.findall(
            r"^ARG ([A-Z][A-Z0-9_]*)",
            WEB_DOCKERFILE_PATH.read_text(encoding="utf-8"),
            flags=re.MULTILINE,
        )
    )
    assert build_time_keys <= dockerfile_arguments
    assert environment["ORYNTELA_ENVIRONMENT"]["value"] == "production"
    assert environment["NEXT_PUBLIC_SITE_URL"]["value"] == "https://oryntela.com.au"
    assert environment["NEXT_PUBLIC_APP_URL"]["value"] == "https://oryntela.com.au"
    assert environment["NEXT_PUBLIC_API_BASE_URL"]["value"] == "https://api.oryntela.com.au"
    assert environment["AUTH_MODE"]["value"] == "clerk"
    assert environment["MOCK_AUTH_ENABLED"]["value"] == "false"
    assert environment["NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY"] == {
        "key": "NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY",
        "scope": "RUN_AND_BUILD_TIME",
        "type": "SECRET",
    }


def test_production_environment_contract_is_unique_portable_and_exact() -> None:
    environment = _production_environment_contract()
    assert environment["ORYNTELA_ENVIRONMENT"] == "production"
    assert environment["API_ENVIRONMENT"] == "production"
    assert environment["API_DATABASE_TLS_MODE"] == "verify_full_custom_ca"
    assert environment["API_DATABASE_POOL_SIZE"] == "5"
    assert environment["API_DATABASE_MAX_OVERFLOW"] == "2"
    assert environment["API_BILLING_SUCCESS_URL"] == "https://oryntela.com.au/billing/success"
    assert environment["API_BILLING_CANCEL_URL"] == "https://oryntela.com.au/settings"
    assert environment["API_BILLING_PORTAL_RETURN_URL"] == "https://oryntela.com.au/settings"
    assert environment["API_MICROSOFT_OAUTH_REDIRECT_URI"] == (
        "https://oryntela.com.au/settings/integrations/microsoft/callback"
    )
    assert environment["API_GOOGLE_OAUTH_REDIRECT_URI"] == (
        "https://oryntela.com.au/settings/integrations/google/callback"
    )
    assert environment["API_HUBSPOT_OAUTH_REDIRECT_URI"] == (
        "https://oryntela.com.au/settings/integrations/hubspot/callback"
    )
    assert environment["API_SALESFORCE_OAUTH_REDIRECT_URI"] == (
        "https://oryntela.com.au/settings/integrations/salesforce/callback"
    )
    assert not any("/Users/" in value or "sqlite" in value.casefold() for value in environment.values())
    for secret_key in (
        "CLERK_SECRET_KEY",
        "DATABASE_URL",
        "API_DATABASE_CA_CERTIFICATE_BASE64",
        "API_VISUAL_S3_ACCESS_KEY_ID",
        "API_VISUAL_S3_SECRET_ACCESS_KEY",
        "API_VISUAL_STORAGE_SIGNING_SECRET",
        "API_BACKUP_ENCRYPTION_KEY",
        "OPENAI_API_KEY",
        "API_STRIPE_SECRET_KEY",
        "API_CONNECTOR_CREDENTIAL_MASTER_KEY",
    ):
        assert environment[secret_key] == ""


def test_independent_backup_lifecycle_covers_every_version_state() -> None:
    policy = json.loads(BACKUP_LIFECYCLE_PATH.read_text(encoding="utf-8"))
    assert isinstance(policy, dict)
    rules = {rule["ID"]: rule for rule in policy["Rules"]}
    expiration = rules["ExpireCurrentRevenueOSBackupsAfter14Days"]
    delete_markers = rules["RemoveExpiredRevenueOSBackupDeleteMarkers"]
    assert expiration == {
        "ID": "ExpireCurrentRevenueOSBackupsAfter14Days",
        "Status": "Enabled",
        "Filter": {"Prefix": "revenueos-private-beta/v1/"},
        "Expiration": {"Days": 14},
        "NoncurrentVersionExpiration": {"NoncurrentDays": 1},
        "AbortIncompleteMultipartUpload": {"DaysAfterInitiation": 1},
    }
    assert delete_markers == {
        "ID": "RemoveExpiredRevenueOSBackupDeleteMarkers",
        "Status": "Enabled",
        "Filter": {"Prefix": "revenueos-private-beta/v1/"},
        "Expiration": {"ExpiredObjectDeleteMarker": True},
    }
