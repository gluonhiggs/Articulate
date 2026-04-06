#!/usr/bin/env bash
# Usage: ./run.sh
set -e

# ── Load config ───────────────────────────────────────────────────────────────
if [ ! -f ".env" ]; then
  echo "Error: .env not found. Copy .env.example to .env and fill in your API keys."
  exit 1
fi
export $(grep -v '^#' ".env" | xargs)

# ── Java check (required for LanguageTool grammar checker) ───────────────────
# Suspend set -e for the install block — brew link commonly exits non-zero on
# Apple Silicon (keg-only formula) and would abort the script prematurely.
set +e
if ! command -v java &>/dev/null; then
  echo "Java not found - attempting installation..."
  if command -v apt-get &>/dev/null; then
    sudo apt-get install -y default-jre-headless
  elif command -v brew &>/dev/null; then
    brew install openjdk
    # keg-only on Apple Silicon: link may fail — ignore non-zero, check below
    brew link --force --overwrite openjdk 2>/dev/null || true
    # Homebrew puts the binary here when the symlink succeeds; add as fallback
    BREW_JAVA="$(brew --prefix openjdk 2>/dev/null)/bin"
    [ -d "$BREW_JAVA" ] && export PATH="$BREW_JAVA:$PATH"
  else
    echo "WARNING: Cannot auto-install Java. Install manually: https://adoptium.net"
    echo "WARNING: Grammar checking will fall back to LanguageTool public API."
  fi

  # Re-check after install attempt
  if ! command -v java &>/dev/null; then
    echo "WARNING: Java still not found after install attempt. Restart your shell or install manually: https://adoptium.net"
    echo "WARNING: Grammar checking will fall back to LanguageTool public API."
  else
    echo "Java installed: $(java -version 2>&1 | head -1)"
  fi
else
  JAVA_VER_LINE="$(java -version 2>&1 | head -1)"
  echo "Java: $JAVA_VER_LINE"
  # Validate minimum version — LanguageTool 6.x requires Java 11+
  JAVA_MAJOR=$(echo "$JAVA_VER_LINE" | grep -oP '(?<=")\d+' | head -1)
  if [ -n "$JAVA_MAJOR" ] && [ "$JAVA_MAJOR" -lt 11 ]; then
    echo "WARNING: Java $JAVA_MAJOR detected - LanguageTool requires Java 11+. Grammar checking may fail."
  fi
fi
set -e

# ── Frontend: staleness check + build if needed ───────────────────────────────
DIST_INDEX="frontend/dist/index.html"
MUST_BUILD=0

if [ ! -f "$DIST_INDEX" ]; then
  echo "Frontend dist not found - building..."
  MUST_BUILD=1
else
  NEWER=$(find frontend/src frontend/index.html frontend/package.json frontend/vite.config.ts \
          -newer "$DIST_INDEX" 2>/dev/null | head -1)
  if [ -n "$NEWER" ]; then
    echo "Frontend source changed ($NEWER) - rebuilding..."
    MUST_BUILD=1
  else
    echo "Frontend dist is up to date, skipping build."
  fi
fi

if [ "$MUST_BUILD" = "1" ]; then
  (cd frontend && bun run build) || { echo "Frontend build failed. Aborting."; exit 1; }
  echo "Frontend built successfully."
fi

# ── Frontend dev server in a new terminal window ──────────────────────────────
ROOT="$(cd "$(dirname "$0")" && pwd)"
echo "Starting frontend dev server (port 5173) in new terminal..."

# Ensure gnome-terminal is available (Linux only)
if [[ "$OSTYPE" == linux* ]] && ! command -v gnome-terminal &>/dev/null; then
  echo "gnome-terminal not found - attempting installation..."
  if command -v apt-get &>/dev/null; then
    sudo apt-get install -y gnome-terminal
  else
    echo "WARNING: Cannot auto-install gnome-terminal. Install it manually or run frontend separately: cd '$ROOT/frontend' && bun run dev"
  fi
fi

_open_terminal() {
  local title="$1" cmd="$2"
  if command -v gnome-terminal &>/dev/null; then
    gnome-terminal --title="$title" -- bash -c "$cmd; exec bash" &
  elif command -v xterm &>/dev/null; then
    xterm -title "$title" -e bash -c "$cmd; exec bash" &
  elif [[ "$OSTYPE" == darwin* ]]; then
    osascript -e "tell app \"Terminal\" to do script \"$cmd\""
  else
    echo "WARNING: No supported terminal emulator found. Run manually: cd '$ROOT/frontend' && bun run dev"
  fi
}

_open_terminal "Articulate frontend" "cd '$ROOT/frontend' && bun run dev"

exec uv run uvicorn backend.main:app --host 0.0.0.0 --port 8000 --workers 1 --reload
