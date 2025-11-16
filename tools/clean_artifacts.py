"""Utility script to remove build artifacts and caches."""

from __future__ import annotations

import argparse
import itertools
from pathlib import Path
import shutil
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]

TOP_LEVEL_DIRS = [
    "build",
    "dist",
    ".mypy_cache",
    ".pytest_cache",
]

TOP_LEVEL_FILES = [
    "acu_simulator.log",
]

GLOB_PATTERNS = [
    "**/__pycache__",
    "**/*.pyc",
]


def _iter_targets() -> Iterable[Path]:
    for rel in itertools.chain(TOP_LEVEL_DIRS, TOP_LEVEL_FILES):
        yield ROOT / rel
    for pattern in GLOB_PATTERNS:
        yield from ROOT.glob(pattern)


def remove_path(path: Path, dry_run: bool) -> None:
    if not path.exists():
        return
    rel = path.relative_to(ROOT)
    action = "Would remove" if dry_run else "Removing"
    print(f"{action} {rel}")
    if dry_run:
        return
    if path.is_dir():
        shutil.rmtree(path, ignore_errors=True)
    else:
        try:
            path.unlink()
        except IsADirectoryError:
            shutil.rmtree(path, ignore_errors=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Remove build/cached artifacts.")
    parser.add_argument(
        "--dry-run", action="store_true", help="List targets without deleting."
    )
    args = parser.parse_args()

    for target in sorted(set(_iter_targets())):
        remove_path(target, args.dry_run)


if __name__ == "__main__":
    main()
