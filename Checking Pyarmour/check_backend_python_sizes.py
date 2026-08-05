#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List


DEFAULT_LIMIT_KB = 48
DEFAULT_ROOT = Path(__file__).resolve().parents[1] / "Codly_Backend"
IGNORED_DIR_NAMES = {
    ".venv",
    "dist",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
}


@dataclass(frozen=True)
class SizeViolation:
    path: Path
    size_bytes: int

    @property
    def size_kb(self) -> float:
        return self.size_bytes / 1024.0


def iter_python_files(root: Path) -> Iterable[Path]:
    for path in root.rglob("*.py"):
        if any(part in IGNORED_DIR_NAMES for part in path.parts):
            continue
        if path.is_file():
            yield path


def check_backend_python_sizes(root: Path, limit_kb: int = DEFAULT_LIMIT_KB) -> List[SizeViolation]:
    limit_bytes = int(limit_kb * 1024)
    violations: List[SizeViolation] = []

    for path in iter_python_files(root):
        try:
            size_bytes = path.stat().st_size
        except OSError:
            continue

        if size_bytes > limit_bytes:
            violations.append(SizeViolation(path=path, size_bytes=size_bytes))

    violations.sort(key=lambda item: (item.size_bytes, str(item.path)), reverse=True)
    return violations


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Check that backend Python files stay under a size limit."
    )
    parser.add_argument(
        "--root",
        default=str(DEFAULT_ROOT),
        help="Backend root to scan (default: Codly_Backend).",
    )
    parser.add_argument(
        "--limit-kb",
        type=int,
        default=DEFAULT_LIMIT_KB,
        help="Maximum allowed file size in KB (default: 48).",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    root = Path(args.root).expanduser().resolve()
    if not root.exists():
        print(f"[Pyarmour] Root folder does not exist: {root}", file=sys.stderr)
        return 2
    if not root.is_dir():
        print(f"[Pyarmour] Root path is not a directory: {root}", file=sys.stderr)
        return 2

    violations = check_backend_python_sizes(root, limit_kb=args.limit_kb)

    total_files = sum(1 for _ in iter_python_files(root))
    limit_label = f"{args.limit_kb} KB"

    print(f"[Pyarmour] Scanned {total_files} Python files under: {root}")

    if not violations:
        print(f"[Pyarmour] OK — every Python file is at or below {limit_label}.")
        return 0

    print(f"[Pyarmour] Found {len(violations)} file(s) above {limit_label}:")
    for violation in violations:
        rel_path = violation.path.relative_to(root) if root in violation.path.parents else violation.path
        print(f" - {rel_path}  ({violation.size_bytes} bytes, {violation.size_kb:.2f} KB)")

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
