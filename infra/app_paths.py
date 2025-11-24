"""Helpers for resolving resource paths in both source and frozen builds."""

from __future__ import annotations

import sys
from functools import lru_cache
from pathlib import Path
from typing import Iterable, Tuple


def _dedupe(paths: Iterable[Path]) -> Tuple[Path, ...]:
    seen = []
    for path in paths:
        resolved = path.resolve()
        if resolved not in seen:
            seen.append(resolved)
    return tuple(seen)


@lru_cache(maxsize=1)
def _candidate_roots() -> Tuple[Path, ...]:
    candidates = []
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            candidates.append(Path(meipass))
        candidates.append(Path(sys.executable).resolve().parent)
    candidates.append(Path(__file__).resolve().parent.parent)
    return _dedupe(candidates)


def get_app_base_dir() -> Path:
    """Return the primary base directory for bundled resources."""

    return _candidate_roots()[0]


def get_dist_dir() -> Path:
    """Return the directory where the executable lives when frozen."""

    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return get_app_base_dir()


def resource_path(
    *parts: str, prefer_write: bool = False, must_exist: bool = False
) -> Path:
    """Resolve a resource path across available roots.

    Args:
        *parts: Path components relative to the resource root.
        prefer_write: When ``True`` the executable directory is preferred,
            which is usually writable by the user.
        must_exist: When ``True`` the first existing path is returned;
            otherwise the first candidate is returned even if it does not yet exist.
    """

    roots = list(_candidate_roots())
    dist_dir = get_dist_dir()
    if prefer_write and dist_dir in roots:
        roots.remove(dist_dir)
        roots.insert(0, dist_dir)

    for root in roots:
        candidate = root.joinpath(*parts)
        if not must_exist or candidate.exists():
            return candidate

    # fall back to the first candidate even if it does not exist
    if roots:
        return roots[0].joinpath(*parts)
    # should never happen, but fallback to current working directory
    return Path.cwd().joinpath(*parts)
