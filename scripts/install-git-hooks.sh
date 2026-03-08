#!/bin/bash
# Install project git hooks from scripts/ into .git/hooks/.
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel)"
HOOKS_SRC="$ROOT/scripts"
HOOKS_DST="$ROOT/.git/hooks"

install_hook() {
  local name="$1"
  cp "$HOOKS_SRC/$name" "$HOOKS_DST/$name"
  chmod +x "$HOOKS_DST/$name"
  echo "  installed .git/hooks/$name"
}

echo "==> Installing git hooks..."
install_hook pre-commit
echo "==> Done."
