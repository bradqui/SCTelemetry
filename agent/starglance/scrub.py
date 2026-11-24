"""Remove aUEC balances from captured frames before they're committed as fixtures."""

from __future__ import annotations

from typing import Any

SCRUBBED = "<scrubbed>"


def is_uec_key(key: str) -> bool:
    return "uec" in key.lower()


def scrub_uec(value: Any) -> Any:
    """A copy of ``value`` with every field whose name mentions UEC replaced by a placeholder."""
    if isinstance(value, dict):
        return {k: (SCRUBBED if is_uec_key(k) else scrub_uec(v)) for k, v in value.items()}
    if isinstance(value, list):
        return [scrub_uec(v) for v in value]
    return value
