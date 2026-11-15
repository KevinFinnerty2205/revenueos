from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import yaml

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
PACKAGE_PATH = REPOSITORY_ROOT / "package.json"
COMPOSE_PATH = REPOSITORY_ROOT / "infra/docker/compose.yml"
CI_WORKFLOW_PATH = REPOSITORY_ROOT / ".github/workflows/ci.yml"
OWNER_DEMO_RUNBOOK_PATH = REPOSITORY_ROOT / "docs/03-engineering/owner-demo-runbook.md"


def test_local_development_services_bind_only_to_loopback() -> None:
    package = cast(dict[str, object], json.loads(PACKAGE_PATH.read_text(encoding="utf-8")))
    scripts = cast(dict[str, str], package["scripts"])
    assert scripts["dev:web"] == "pnpm --filter @revenueos/web dev --hostname 127.0.0.1"

    compose = cast(dict[str, object], yaml.safe_load(COMPOSE_PATH.read_text(encoding="utf-8")))
    services = cast(dict[str, object], compose["services"])
    postgres = cast(dict[str, object], services["postgres"])
    assert postgres["ports"] == ["127.0.0.1:5432:5432"]


def test_local_and_full_stack_api_servers_disable_query_string_access_logs() -> None:
    package = cast(dict[str, object], json.loads(PACKAGE_PATH.read_text(encoding="utf-8")))
    scripts = cast(dict[str, str], package["scripts"])
    assert "--no-access-log" in scripts["dev:api"].split()

    workflow = cast(dict[str, object], yaml.safe_load(CI_WORKFLOW_PATH.read_text(encoding="utf-8")))
    jobs = cast(dict[str, object], workflow["jobs"])
    conversation_persistence = cast(dict[str, object], jobs["conversation-persistence"])
    steps = cast(list[dict[str, object]], conversation_persistence["steps"])
    start_command = next(
        cast(str, step["run"]) for step in steps if step.get("name") == "Run browser-to-API persistence acceptance"
    )
    assert "--no-access-log" in start_command.split()


def test_owner_demo_runbook_bootstraps_identity_before_seed_and_keeps_boundaries() -> None:
    runbook = OWNER_DEMO_RUNBOOK_PATH.read_text(encoding="utf-8")

    api_start = runbook.index("pnpm dev:api")
    readiness = runbook.index("http://localhost:8000/ready")
    seed = runbook.index("pnpm demo:owner")
    worker_start = runbook.index("pnpm dev:worker")
    web_start = runbook.index("pnpm dev:web")
    assert api_start < readiness < seed < worker_start < web_start

    for expected in (
        '"dataset_version": 21',
        "real Northstar-linked Task",
        "**Members**",
        "Do not queue deletion",
        "**Create → Studio**",
        "**Rotate link**",
        "select **Last quarter**",
        "**1 July to 30 September 2026**",
        "billing, checkout and Credits remain disabled",
    ):
        assert expected in runbook
