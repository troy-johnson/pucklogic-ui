#!/bin/bash
set -euo pipefail

# Only run in remote (Claude Code on the web) environments
if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"

echo "==> PuckLogic session start hook"

# ── Node / Turborepo (root or apps/web) ─────────────────────────────────────
if [ -f "$PROJECT_DIR/package.json" ]; then
  echo "==> Installing Node.js dependencies (root)..."
  cd "$PROJECT_DIR"
  npm install
fi

# ── Python / FastAPI (apps/api or root) ─────────────────────────────────────
install_python_deps() {
  local dir="$1"
  if [ -f "$dir/pyproject.toml" ]; then
    echo "==> Installing Python dependencies from pyproject.toml in $dir..."
    cd "$dir"
    pip install -e ".[dev]" --quiet
  elif [ -f "$dir/requirements.txt" ]; then
    echo "==> Installing Python dependencies from requirements.txt in $dir..."
    pip install -r "$dir/requirements.txt" --quiet
  fi
}

install_python_deps "$PROJECT_DIR"
install_python_deps "$PROJECT_DIR/apps/api"

echo "==> Session start hook complete."
