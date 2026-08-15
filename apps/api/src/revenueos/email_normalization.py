from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class NormalizedEmail:
    body: str
    quote_handling: Literal["none", "stripped", "ambiguous"]


_reply_header = re.compile(
    r"^(?:on .{1,200} wrote:|from:\s*.{1,200}|sent:\s*.{1,200}|-{2,}\s*original message\s*-{2,})$",
    flags=re.IGNORECASE,
)


def normalize_plain_text_email(body: str) -> NormalizedEmail:
    """Strip only unambiguous quoted history/signatures; ambiguous content stays intact."""

    canonical = body.replace("\r\n", "\n").replace("\r", "\n").strip()
    if any(
        (ord(character) < 32 and character not in {"\t", "\n", "\r"}) or ord(character) == 127
        for character in canonical
    ):
        raise ValueError("Email body contains unsupported control characters.")
    lines = canonical.splitlines()
    boundary: int | None = None
    ambiguous = False
    for index, line in enumerate(lines):
        stripped = line.strip()
        if stripped == "--":
            boundary = index
            break
        if stripped.startswith(">"):
            boundary = index
            break
        if _reply_header.fullmatch(stripped):
            if stripped.lower().startswith("from:") and index < 2:
                ambiguous = True
                continue
            boundary = index
            break
        if stripped.lower().startswith(("begin forwarded message", "forwarded message")):
            boundary = index
            break
    if boundary is None:
        return NormalizedEmail(body=canonical, quote_handling="ambiguous" if ambiguous else "none")
    retained = "\n".join(lines[:boundary]).strip()
    if not retained:
        return NormalizedEmail(body=canonical, quote_handling="ambiguous")
    return NormalizedEmail(body=retained, quote_handling="stripped")
