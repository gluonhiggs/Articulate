# Contributing to Articulate

Thanks for working on Articulate. This doc covers the local setup and the `make` targets that mirror what GitHub Actions runs, so you can catch CI failures before they hit a PR (or worse, a tagged release).

## Development environment

Articulate's toolchain:

- **[uv](https://docs.astral.sh/uv/)** — Python backend (runs the API, manages deps, drives PyInstaller)
- **[bun](https://bun.sh/)** — React frontend + Electron wrapper (install, build, test)
- **[pre-commit](https://pre-commit.com/)** — git hooks (fast lint on commit, `make ci` on push)
- **GNU make** — the one command you run; it calls the three above

### Prerequisites (per-machine, one-time)

#### macOS

```bash
# Homebrew: https://brew.sh if you don't have it
brew install git uv bun
# `make` is already installed via Xcode Command Line Tools (`xcode-select --install`)
```

#### Linux (Ubuntu/Debian)

```bash
sudo apt update && sudo apt install git build-essential
# build-essential includes make + a C toolchain
curl -LsSf https://astral.sh/uv/install.sh | sh
curl -fsSL https://bun.sh/install | bash
# Restart your shell so the new uv/bun binaries are on PATH
```

Other distros: install `git` + `make` from your package manager, then `uv` and `bun` via their install scripts above.

#### Windows

1. Install [Git for Windows](https://git-scm.com/download/win) — gives you `git` plus **Git Bash**, which you'll use to run `make` commands.
2. Install [scoop](https://scoop.sh) (no admin required):
   ```powershell
   Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
   irm get.scoop.sh | iex
   ```
3. Install `uv`, `bun`, and `make` via scoop:
   ```powershell
   scoop install uv bun make
   ```
4. **Run all `make` commands from Git Bash, NOT PowerShell.** The Makefile declares `SHELL := /bin/bash` — PowerShell can't resolve that path and recipes will fail. Right-click the repo folder → "Open Git Bash here," or launch Git Bash from Start and `cd` to the repo.

> If you prefer Chocolatey over scoop: `choco install git uv bun make` (admin required). If you want zero package managers: download `make-4.4.1-without-guile-w32-bin.zip` from [ezwinports](https://sourceforge.net/projects/ezwinports/files/) and add its `bin/` to your PATH manually.

### Per-clone setup

Once the prerequisites above are on your machine, for each fresh clone:

```bash
uv tool install pre-commit
git clone https://github.com/gluonhiggs/Articulate.git
cd Articulate
make install
```

`make install` does the full env: backend deps (`uv sync`), frontend deps (`bun install` in `frontend/`), electron deps (`bun install` in `electron/`), and wires the pre-commit + pre-push git hooks into `.git/hooks/`.

> **Why `uv tool install pre-commit` instead of bundling it in the project venv?** pre-commit is a machine-level developer tool you'll reuse across every repo. `uv tool install` drops it in `~/.local/share/uv/tools/` (or the Windows equivalent) — nothing touches `pyproject.toml` or the project `.venv/`. You install it once per machine, not once per clone.

## Making changes

### Before committing

The pre-commit hook runs automatically on `git commit` and will auto-fix most style issues (ruff lint + format, trailing whitespace, YAML/TOML syntax). If it changes anything, re-stage and commit again.

To run the same checks manually:

```bash
make format    # auto-fix ruff lint + format violations
make check     # ruff check + frontend typecheck + electron typecheck
```

### Before pushing

Run the same thing CI runs:

```bash
make ci        # check + test (backend pytest + frontend vitest)
```

This mirrors `.github/workflows/ci.yml`. If `make ci` passes locally, branch CI should pass too. The pre-push hook also runs `make ci` automatically for every `git push` to a branch. Bypass with `git push --no-verify` in emergencies.

### Before tagging a release

Tagging is the expensive event: `release.yml` runs a 5-leg OS × variant matrix (~20 min) and publishes installers to GitHub Releases on success. Validate locally first:

```bash
make release-cpu   # ~10 min: PyInstaller bundle + verify + electron installer (CPU variant)
```

The pre-push hook runs `make release-cpu` automatically when you push a tag matching `v*.*.*`. If it fails, the push is aborted and no version number is burned.

`release-gpu` exists for the CUDA variant but is optional locally — the CPU path catches the same class of bundle-shape bugs.

## Target reference

| Target | What it does |
|---|---|
| `install` | Full dev env: backend + frontend + electron + pre-commit hooks |
| `test` | Backend pytest + frontend vitest (mirrors CI) |
| `check` | Ruff lint + frontend typecheck + electron typecheck |
| `format` | Auto-fix ruff lint + format |
| `ci` | `check` + `test`. Run before every push. |
| `release-cpu` | Full CPU release artifacts (PyInstaller + electron installer) |
| `release-gpu` | Full GPU release artifacts (adds CUDA runtime) |
| `clean` | Remove `dist/`, `build/`, `frontend/dist/`, `electron/dist*` |

Run `make help` anytime to see the full list including sub-targets.

## Pull requests

1. Fork + branch off `main`.
2. `make ci` passes locally.
3. Open the PR against `main`. CI re-runs `ci.yml`; the 5-leg release build runs only on tag push.
4. One reviewer approval + green CI → merge.
