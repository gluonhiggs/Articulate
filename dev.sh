#!/usr/bin/env bash
# Usage: ./dev.sh [auto|laptop|pc|gemini]
# Starts backend (run.sh) and frontend (bun run dev) in two terminal windows.
PROFILE=${1:-auto}
ROOT="$(cd "$(dirname "$0")" && pwd)"

open_terminal() {
  local title="$1"; shift
  local cmd="$*"
  if command -v gnome-terminal &>/dev/null; then
    gnome-terminal --title="$title" -- bash -c "$cmd; exec bash"
  elif command -v xterm &>/dev/null; then
    xterm -title "$title" -e bash -c "$cmd; exec bash" &
  elif [[ "$OSTYPE" == darwin* ]]; then
    osascript -e "tell app \"Terminal\" to do script \"$cmd\""
  else
    echo "No supported terminal emulator found. Run manually:"
    echo "  $cmd"
  fi
}

echo "Starting backend..."
open_terminal "Articulate backend" "cd '$ROOT' && ./run.sh $PROFILE"

echo "Starting frontend..."
open_terminal "Articulate frontend" "cd '$ROOT/frontend' && bun run dev"
