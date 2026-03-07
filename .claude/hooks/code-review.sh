#!/bin/bash
# PuckLogic Code Review Hook
# Triggered by PostToolUse (Edit, Write, MultiEdit) to run linting on changed files.
# Input: JSON from Claude Code via stdin (tool name + input/output)

set -uo pipefail

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"

# Parse the file path from the tool input JSON (stdin)
TOOL_INPUT="$(cat)"
FILE_PATH="$(echo "$TOOL_INPUT" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    # tool_input contains the parameters passed to the tool
    inp = data.get('tool_input', {})
    path = inp.get('file_path') or inp.get('path') or ''
    print(path)
except Exception:
    print('')
" 2>/dev/null)"

if [ -z "$FILE_PATH" ]; then
  exit 0
fi

# Make path absolute if relative
if [[ "$FILE_PATH" != /* ]]; then
  FILE_PATH="$PROJECT_DIR/$FILE_PATH"
fi

# Skip if file doesn't exist
if [ ! -f "$FILE_PATH" ]; then
  exit 0
fi

ISSUES_FOUND=0

# ── Python files → ruff ─────────────────────────────────────────────────────
if [[ "$FILE_PATH" == *.py ]]; then
  if command -v ruff &>/dev/null; then
    echo "==> [code-review] ruff: $FILE_PATH"
    if ! ruff check --quiet "$FILE_PATH" 2>&1; then
      ISSUES_FOUND=1
    fi
  fi
fi

# ── TypeScript / JavaScript files → ESLint ──────────────────────────────────
if [[ "$FILE_PATH" == *.ts || "$FILE_PATH" == *.tsx || "$FILE_PATH" == *.js || "$FILE_PATH" == *.jsx ]]; then
  # Find the nearest package.json to locate the eslint config
  DIR="$(dirname "$FILE_PATH")"
  while [ "$DIR" != "/" ] && [ ! -f "$DIR/package.json" ]; do
    DIR="$(dirname "$DIR")"
  done

  if [ -f "$DIR/package.json" ] && command -v pnpm &>/dev/null; then
    ESLINT_BIN="$DIR/node_modules/.bin/eslint"
    if [ -f "$ESLINT_BIN" ]; then
      echo "==> [code-review] eslint: $FILE_PATH"
      if ! "$ESLINT_BIN" --quiet "$FILE_PATH" 2>&1; then
        ISSUES_FOUND=1
      fi
    fi
  fi
fi

# ── TypeScript type-check (tsconfig present) ─────────────────────────────────
if [[ "$FILE_PATH" == *.ts || "$FILE_PATH" == *.tsx ]]; then
  DIR="$(dirname "$FILE_PATH")"
  while [ "$DIR" != "/" ] && [ ! -f "$DIR/tsconfig.json" ]; do
    DIR="$(dirname "$DIR")"
  done

  if [ -f "$DIR/tsconfig.json" ]; then
    TSC_BIN="$DIR/node_modules/.bin/tsc"
    if [ -f "$TSC_BIN" ]; then
      echo "==> [code-review] tsc: $FILE_PATH"
      if ! "$TSC_BIN" --noEmit --project "$DIR/tsconfig.json" 2>&1 | grep -E "error TS" | head -20; then
        : # tsc exits non-zero even on success sometimes; grep handles it
      fi
    fi
  fi
fi

if [ "$ISSUES_FOUND" -eq 1 ]; then
  echo "==> [code-review] Issues found — review the output above before committing."
fi

exit 0
