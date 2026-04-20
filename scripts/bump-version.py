"""
Bump all repository version strings to a new semver.

Files updated:
  electron/package.json           .version
  pyproject.toml                  version = "..."
  frontend/package.json           .version
  frontend/package-lock.json      .version and .packages[""].version (two lines, no reformat)
  backend/main.py                 version="..." in FastAPI constructor

Preconditions checked here:
  - VERSION matches x.y.z
  - VERSION > current version in electron/package.json

Git preconditions (clean tree, on main, tag absent) are checked by `make tag`.

Usage:
  python scripts/bump-version.py 0.2.0
"""

import json
import re
import sys
from pathlib import Path


def parse_semver(v: str) -> tuple[int, int, int]:
    m = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)", v)
    if not m:
        raise ValueError(f"Not a valid semver (x.y.z): {v!r}")
    return int(m.group(1)), int(m.group(2)), int(m.group(3))


def _regex_replace_once(path: Path, pattern: str, replacement: str, flags: int = 0) -> None:
    content = path.read_text(encoding="utf-8")
    new_content, n = re.subn(pattern, replacement, content, count=1, flags=flags)
    if n == 0:
        raise RuntimeError(f"Pattern {pattern!r} not found in {path}")
    path.write_text(new_content, encoding="utf-8")


def bump_electron_package(repo: Path, new_version: str) -> None:
    path = repo / "electron" / "package.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["version"] = new_version
    # json.dumps preserves key order from CPython 3.7+; two-space indent matches repo style
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def bump_pyproject(repo: Path, new_version: str) -> None:
    _regex_replace_once(
        repo / "pyproject.toml",
        r'^version = "[^"]*"',
        f'version = "{new_version}"',
        flags=re.MULTILINE,
    )


def bump_frontend_package(repo: Path, new_version: str) -> None:
    path = repo / "frontend" / "package.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["version"] = new_version
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def bump_package_lock(repo: Path, old_version: str, new_version: str) -> None:
    # Replace only the two project-owned occurrences without reformatting the whole lockfile.
    # (Dependency versions are different strings; there are exactly 2 matches for the project version.)
    path = repo / "frontend" / "package-lock.json"
    content = path.read_text(encoding="utf-8")
    pattern = re.escape(f'"version": "{old_version}"')
    replacement = f'"version": "{new_version}"'
    new_content, n = re.subn(pattern, replacement, content, count=2)
    if n == 0:
        raise RuntimeError(f'No occurrences of "version": "{old_version}" found in {path}')
    path.write_text(new_content, encoding="utf-8")


def bump_backend_main(repo: Path, new_version: str) -> None:
    _regex_replace_once(
        repo / "backend" / "main.py",
        r'version="[^"]*"',
        f'version="{new_version}"',
    )


def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: python scripts/bump-version.py <VERSION>", file=sys.stderr)
        sys.exit(1)

    new_version = sys.argv[1]
    try:
        new_tuple = parse_semver(new_version)
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    repo = Path(__file__).resolve().parent.parent

    # Read current version from electron/package.json (authoritative)
    electron_pkg = repo / "electron" / "package.json"
    current_version = json.loads(electron_pkg.read_text(encoding="utf-8"))["version"]
    try:
        current_tuple = parse_semver(current_version)
    except ValueError:
        current_tuple = (0, 0, 0)

    if new_tuple <= current_tuple:
        print(
            f"ERROR: new version {new_version} must be greater than current {current_version}",
            file=sys.stderr,
        )
        sys.exit(1)

    # Read current frontend/package-lock.json version before updating anything
    lock_path = repo / "frontend" / "package-lock.json"
    lock_current = json.loads(lock_path.read_text(encoding="utf-8")).get("version", current_version)

    print(f"Bumping {current_version} -> {new_version}")

    bump_electron_package(repo, new_version)
    print("  electron/package.json")

    bump_pyproject(repo, new_version)
    print("  pyproject.toml")

    bump_frontend_package(repo, new_version)
    print("  frontend/package.json")

    bump_package_lock(repo, lock_current, new_version)
    print("  frontend/package-lock.json")

    bump_backend_main(repo, new_version)
    print("  backend/main.py")

    print(f"\nAll version strings set to {new_version}.")


if __name__ == "__main__":
    main()
