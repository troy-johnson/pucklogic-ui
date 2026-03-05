#!/bin/bash
set -euo pipefail

# Only run in remote (Claude Code on the web) environments
if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"

echo "==> PuckLogic session start hook"

# ── Node / Turborepo (pnpm) ──────────────────────────────────────────────────
if [ -f "$PROJECT_DIR/package.json" ]; then
  echo "==> Installing Node.js dependencies (pnpm)..."
  cd "$PROJECT_DIR"
  # Install pnpm if not available
  if ! command -v pnpm &>/dev/null; then
    npm install -g pnpm
  fi
  pnpm install
fi

# ── Python / FastAPI (apps/api) ──────────────────────────────────────────────
if [ -f "$PROJECT_DIR/apps/api/pyproject.toml" ]; then
  echo "==> Installing Python dependencies (apps/api)..."
  cd "$PROJECT_DIR/apps/api"
  pip install -e ".[dev]" --quiet
fi

echo "==> Session start hook complete."
