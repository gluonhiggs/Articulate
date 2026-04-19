"""
Ensure the electron-builder winCodeSign cache is populated on Windows.

On Windows without Developer Mode, 7-Zip cannot create macOS symlinks inside
the winCodeSign archive (darwin/10.12/lib/libcrypto.dylib etc.) and exits with
code 2. electron-builder treats that as a fatal error and retries forever.

This script runs 7-Zip ourselves, tolerates exit code 2 (partial extraction),
and copies the result to the expected cache directory if the Windows binaries
are present. The macOS symlinks are irrelevant on Windows.

Called from: Makefile electron-package target (Windows only via sys.platform).
"""

import os
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

WINCOSIGN_VERSION = "2.6.0"
WINCOSIGN_URL = (
    f"https://github.com/electron-userland/electron-builder-binaries"
    f"/releases/download/winCodeSign-{WINCOSIGN_VERSION}"
    f"/winCodeSign-{WINCOSIGN_VERSION}.7z"
)
REQUIRED_FILES = ["rcedit-x64.exe", "rcedit-ia32.exe"]


def electron_builder_cache() -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA") or str(
        Path.home() / "AppData" / "Local"
    )
    return Path(local_app_data) / "electron-builder" / "Cache" / "winCodeSign"


def find_7za(script_dir: Path) -> Path:
    candidate = (
        script_dir.parent
        / "electron"
        / "node_modules"
        / "7zip-bin"
        / "win"
        / "x64"
        / "7za.exe"
    )
    if candidate.exists():
        return candidate
    raise FileNotFoundError(
        "7za.exe not found in electron/node_modules — run `bun install` first"
    )


def main() -> None:
    if sys.platform != "win32":
        return

    cache_root = electron_builder_cache()
    target = cache_root / f"winCodeSign-{WINCOSIGN_VERSION}"

    if target.exists() and any((target / f).exists() for f in REQUIRED_FILES):
        print(f"winCodeSign cache already present at {target}")
        return

    script_dir = Path(__file__).parent
    try:
        seven_za = find_7za(script_dir)
    except FileNotFoundError as exc:
        print(f"WARNING: {exc}. Skipping winCodeSign cache population.", file=sys.stderr)
        return

    cache_root.mkdir(parents=True, exist_ok=True)
    archive = cache_root / f"winCodeSign-{WINCOSIGN_VERSION}.7z"

    if not archive.exists():
        print(f"Downloading winCodeSign {WINCOSIGN_VERSION}...")
        urllib.request.urlretrieve(WINCOSIGN_URL, archive)
        print("Downloaded.")

    with tempfile.TemporaryDirectory(dir=cache_root) as tmp:
        tmp_path = Path(tmp)
        result = subprocess.run(
            [str(seven_za), "x", "-snld", "-bd", str(archive), f"-o{tmp_path}"],
            capture_output=True,
            text=True,
        )
        # Exit code 2 = errors (macOS symlinks on Windows without Developer Mode).
        # Check that the Windows binaries we actually need are present.
        windows_ok = all((tmp_path / f).exists() for f in REQUIRED_FILES)
        if result.returncode not in (0, 2) or not windows_ok:
            print(result.stdout, file=sys.stderr)
            print(result.stderr, file=sys.stderr)
            print(
                "ERROR: winCodeSign extraction failed and Windows binaries are missing.",
                file=sys.stderr,
            )
            sys.exit(1)

        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(tmp_path, target)

    print(f"winCodeSign cache populated at {target}")


if __name__ == "__main__":
    main()
