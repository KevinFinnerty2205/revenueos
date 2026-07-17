"""Fail CI on obvious committed secrets or Sprint 3 scope violations."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

SECRET_PATTERNS = {
    "AWS access key": re.compile(rb"\bAKIA[0-9A-Z]{16}\b"),
    "GitHub token": re.compile(rb"\bgh[pousr]_[A-Za-z0-9]{30,}\b"),
    "OpenAI API key": re.compile(rb"\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}\b"),
    "private key": re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
}

OUT_OF_SCOPE_PREFIXES = (
    "apps/api/src/revenueos/ai/",
    "apps/api/src/revenueos/background_jobs/",
    "apps/api/src/revenueos/billing/",
    "apps/api/src/revenueos/integrations/",
    "apps/api/src/revenueos/transcription/",
    "apps/api/src/revenueos/workers/",
    "apps/mobile/",
)


def tracked_files() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        check=True,
        capture_output=True,
    )
    return [Path(item.decode()) for item in result.stdout.split(b"\0") if item]


def main() -> int:
    files = tracked_files()
    violations: list[str] = []

    for path in files:
        relative_path = path.as_posix()
        if relative_path.startswith(OUT_OF_SCOPE_PREFIXES):
            violations.append(f"out-of-scope implementation path: {relative_path}")
        try:
            content = path.read_bytes()
        except OSError as error:
            violations.append(f"could not inspect {relative_path}: {error}")
            continue
        if b"\0" in content:
            continue
        for label, pattern in SECRET_PATTERNS.items():
            if pattern.search(content):
                violations.append(f"possible {label}: {relative_path}")

    if violations:
        print("Repository audit failed:")
        for violation in violations:
            print(f"- {violation}")
        return 1

    print(f"Repository audit passed for {len(files)} tracked files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
