"""Send only what changed: a JSON merge patch between two states (spec §4, decision 13).

Used agent -> hub (snapshot deltas) and hub -> viewer (roster and member deltas).

The rules are RFC 7386 with one difference, because our states always carry
every key and ``null`` means "not known right now":

- an object in the patch is merged key by key, recursively;
- anything else (number, string, list, ``null``) replaces the old value;
- ``null`` sets the value to null. Keys are never deleted.

A key that disappears from the new state (e.g. a warning light the game stops
sending) is patched to ``null``.

Pure Python, no dependencies: the ButlerBot cog (Python 3.11) may import it.
"""

from __future__ import annotations

from typing import Any

_MISSING = object()


def diff(old: Any, new: Any) -> Any:
    """The patch that turns ``old`` into ``new``, or ``_MISSING`` when they're equal.

    Use :func:`make_patch` for the public form (``None`` when nothing changed).
    """
    if isinstance(old, dict) and isinstance(new, dict):
        out: dict[str, Any] = {}
        for key, value in new.items():
            sub = diff(old.get(key, _MISSING), value) if key in old else value
            if sub is not _MISSING:
                out[key] = sub
        for key in old.keys() - new.keys():
            if old[key] is not None:
                out[key] = None
        return out if out else _MISSING
    if old is _MISSING:
        return new
    # bool is an int in Python: True == 1. Compare types too, or a flip from 1 to True is lost.
    if type(old) is type(new) and old == new:
        return _MISSING
    return new


def make_patch(old: dict | None, new: dict | None) -> dict | None:
    """A merge patch from ``old`` to ``new`` (both whole states), or None if unchanged.

    When ``old`` is None (nothing sent yet) the patch is the whole of ``new``.
    """
    if old is None:
        return new
    if new is None:
        raise ValueError("a state can't be patched to None; send a full state instead")
    result = diff(old, new)
    return None if result is _MISSING else result


def apply_patch(target: dict | None, patch: dict) -> dict:
    """A new state: ``target`` with ``patch`` merged in. ``target`` is not modified."""
    out = dict(target) if isinstance(target, dict) else {}
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = apply_patch(out[key], value)
        else:
            out[key] = value
    return out
