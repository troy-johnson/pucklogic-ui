#!/usr/bin/env bash
# codex_review.sh — Run AI code review for the current PR.
#
# Runs Gemini (gemini-2.5-pro) and Codex (o4-mini) in parallel via opencode,
# then prints combined findings for triage.
#
# Usage:
#   ./scripts/codex_review.sh              # auto-detects current branch's PR
#   ./scripts/codex_review.sh 42           # explicit PR number
#   BOT_ONLY=1 ./scripts/codex_review.sh   # try GitHub Codex bot only, no CLI fallback
#   SKIP_GEMINI=1 ./scripts/codex_review.sh   # skip Gemini (usage limit)
#   SKIP_CODEX=1 ./scripts/codex_review.sh    # skip Codex (usage limit)

set -euo pipefail

PR_NUMBER="${1:-}"
BOT_ONLY="${BOT_ONLY:-0}"
SKIP_GEMINI="${SKIP_GEMINI:-0}"
SKIP_CODEX="${SKIP_CODEX:-0}"
WAIT_SECONDS=90
POLL_INTERVAL=10

# ---------------------------------------------------------------------------
# Resolve PR number
# ---------------------------------------------------------------------------
if [[ -z "$PR_NUMBER" ]]; then
  PR_NUMBER=$(gh pr view --json number --jq '.number' 2>/dev/null || echo "")
  if [[ -z "$PR_NUMBER" ]]; then
    echo "ERROR: No open PR for current branch. Push and open a PR first."
    exit 1
  fi
fi

echo "==> PR #${PR_NUMBER}: starting AI code review"

# ---------------------------------------------------------------------------
# Helper: check if Codex bot review exists
# ---------------------------------------------------------------------------
codex_bot_review_exists() {
  gh api "repos/{owner}/{repo}/pulls/${PR_NUMBER}/reviews" \
    --jq '.[].user.login' 2>/dev/null \
    | grep -qi "codex" && return 0
  gh api "repos/{owner}/{repo}/issues/${PR_NUMBER}/comments" \
    --jq '.[].user.login' 2>/dev/null \
    | grep -qi "codex" && return 0
  return 1
}

# ---------------------------------------------------------------------------
# Helper: detect usage limit errors in opencode output
# ---------------------------------------------------------------------------
is_usage_error() {
  local output="$1"
  echo "$output" | grep -qiE "rate.?limit|quota|usage.?limit|insufficient.?credits|429|unauthorized|authentication|invalid.?api.?key|no.?credits" && return 0
  return 1
}

# ---------------------------------------------------------------------------
# Strategy 1: GitHub Codex bot (optional)
# ---------------------------------------------------------------------------
if [[ "$BOT_ONLY" == "1" ]]; then
  echo "==> Requesting Codex bot review via PR comment..."
  gh pr comment "$PR_NUMBER" --body "@codexbot review"
  echo "==> Waiting up to ${WAIT_SECONDS}s for Codex bot response..."
  elapsed=0
  while [[ $elapsed -lt $WAIT_SECONDS ]]; do
    sleep "$POLL_INTERVAL"
    elapsed=$((elapsed + POLL_INTERVAL))
    if codex_bot_review_exists; then
      echo "==> Codex bot review received."
      gh pr view "$PR_NUMBER" --json url --jq '.url'
      exit 0
    fi
    echo "    ...waiting (${elapsed}s elapsed)"
  done
  echo "==> Codex bot did not respond within ${WAIT_SECONDS}s. Run without BOT_ONLY=1 to use CLI fallback."
  exit 1
fi

# ---------------------------------------------------------------------------
# Fetch PR content
# ---------------------------------------------------------------------------
if ! command -v opencode &>/dev/null; then
  echo "ERROR: 'opencode' CLI not found. Install from https://opencode.ai"
  exit 1
fi

echo "==> Fetching PR #${PR_NUMBER} diff..."
DIFF=$(gh pr diff "$PR_NUMBER" 2>/dev/null)
if [[ -z "$DIFF" ]]; then
  echo "ERROR: Could not fetch PR diff."
  exit 1
fi

PR_TITLE=$(gh pr view "$PR_NUMBER" --json title --jq '.title')
PR_BODY=$(gh pr view "$PR_NUMBER" --json body --jq '.body')

SHARED_CONTEXT="PR #${PR_NUMBER}: ${PR_TITLE}

Description:
${PR_BODY}

Diff:
${DIFF}"

CODEX_PROMPT="You are reviewing a pull request for the PuckLogic fantasy hockey draft kit (Python/FastAPI backend, pytest, Supabase PostgreSQL).

${SHARED_CONTEXT}

Review for:
1. Bugs or logic errors
2. Silent failures or inadequate error handling
3. Code quality: ruff compliance, type annotations, logging not print
4. Test coverage gaps
5. API contract violations or schema misuse

For each issue: severity (Critical/Important/Minor), file:line, description, suggested fix.
Be concise. Skip praise."

GEMINI_PROMPT="You are reviewing a pull request for the PuckLogic fantasy hockey draft kit (Python/FastAPI backend, pytest, Supabase PostgreSQL).

${SHARED_CONTEXT}

Review for:
1. Security surface: auth gaps, data exposure, missing input validation, RLS policy implications
2. Ecosystem concerns: deprecated patterns, better library alternatives, maintainability
3. Silent failures: catch blocks that swallow errors, fallback values that mask problems
4. Cross-cutting concerns: does this change have implications for other parts of the system not in the diff?

For each issue: severity (Critical/Important/Minor), file:line, description, suggested fix.
Be concise. Skip praise."

# ---------------------------------------------------------------------------
# Strategy 2: Run Gemini and Codex in parallel via opencode CLI
# ---------------------------------------------------------------------------
GEMINI_OUTPUT=""
CODEX_OUTPUT=""
GEMINI_FAILED=0
CODEX_FAILED=0

if [[ "$SKIP_GEMINI" == "1" ]]; then
  echo "==> Skipping Gemini review (SKIP_GEMINI=1)"
else
  echo "==> Starting Gemini (gemini-2.5-pro) review..."
  GEMINI_OUTPUT=$(opencode run -m google/gemini-2.5-pro "$GEMINI_PROMPT" 2>&1) || GEMINI_FAILED=$?
fi

if [[ "$SKIP_CODEX" == "1" ]]; then
  echo "==> Skipping Codex review (SKIP_CODEX=1)"
else
  echo "==> Starting Codex (openai/o4-mini) review..."
  CODEX_OUTPUT=$(opencode run -m openai/o4-mini "$CODEX_PROMPT" 2>&1) || CODEX_FAILED=$?
fi

# ---------------------------------------------------------------------------
# Handle failures
# ---------------------------------------------------------------------------
GEMINI_UNAVAILABLE=0
CODEX_UNAVAILABLE=0

if [[ $GEMINI_FAILED -ne 0 ]] && [[ "$SKIP_GEMINI" != "1" ]]; then
  if is_usage_error "$GEMINI_OUTPUT"; then
    GEMINI_UNAVAILABLE=1
    echo ""
    echo "⚠️  GEMINI REVIEW FAILED — likely usage limit or auth issue."
    echo "   Output: $(echo "$GEMINI_OUTPUT" | head -3)"
    echo "   Options:"
    echo "     (1) Retry:          ./scripts/codex_review.sh ${PR_NUMBER}"
    echo "     (2) Skip Gemini:    SKIP_GEMINI=1 ./scripts/codex_review.sh ${PR_NUMBER}"
    echo "     (3) Skip all:       SKIP_GEMINI=1 SKIP_CODEX=1 ./scripts/codex_review.sh ${PR_NUMBER}"
    echo ""
    read -r -p "Continue with Codex-only review? [y/N] " CONTINUE_WITHOUT_GEMINI
    if [[ "$CONTINUE_WITHOUT_GEMINI" != "y" && "$CONTINUE_WITHOUT_GEMINI" != "Y" ]]; then
      echo "Exiting. Re-run with one of the options above."
      exit 1
    fi
  else
    echo "ERROR: Gemini review failed for an unexpected reason:"
    echo "$GEMINI_OUTPUT"
    exit 1
  fi
fi

if [[ $CODEX_FAILED -ne 0 ]] && [[ "$SKIP_CODEX" != "1" ]]; then
  if is_usage_error "$CODEX_OUTPUT"; then
    CODEX_UNAVAILABLE=1
    echo ""
    echo "⚠️  CODEX REVIEW FAILED — likely usage limit or auth issue."
    echo "   Output: $(echo "$CODEX_OUTPUT" | head -3)"
    echo "   Options:"
    echo "     (1) Retry:          ./scripts/codex_review.sh ${PR_NUMBER}"
    echo "     (2) Skip Codex:     SKIP_CODEX=1 ./scripts/codex_review.sh ${PR_NUMBER}"
    echo "     (3) Skip all:       SKIP_GEMINI=1 SKIP_CODEX=1 ./scripts/codex_review.sh ${PR_NUMBER}"
    echo ""
    read -r -p "Continue with Gemini-only review? [y/N] " CONTINUE_WITHOUT_CODEX
    if [[ "$CONTINUE_WITHOUT_CODEX" != "y" && "$CONTINUE_WITHOUT_CODEX" != "Y" ]]; then
      echo "Exiting. Re-run with one of the options above."
      exit 1
    fi
  else
    echo "ERROR: Codex review failed for an unexpected reason:"
    echo "$CODEX_OUTPUT"
    exit 1
  fi
fi

if [[ $GEMINI_UNAVAILABLE -eq 1 ]] && [[ $CODEX_UNAVAILABLE -eq 1 ]]; then
  echo ""
  echo "⚠️  Both reviewers unavailable. No external review produced."
  echo "   Proceed with manual code review only, or retry later."
  exit 1
fi

# ---------------------------------------------------------------------------
# Print combined findings
# ---------------------------------------------------------------------------
echo ""
echo "================================================================"
echo "  AI CODE REVIEW — PR #${PR_NUMBER}: ${PR_TITLE}"
echo "================================================================"

if [[ -n "$GEMINI_OUTPUT" ]] && [[ $GEMINI_UNAVAILABLE -eq 0 ]]; then
  echo ""
  echo "--- GEMINI (gemini-2.5-pro) ---"
  echo "$GEMINI_OUTPUT"
fi

if [[ -n "$CODEX_OUTPUT" ]] && [[ $CODEX_UNAVAILABLE -eq 0 ]]; then
  echo ""
  echo "--- CODEX (openai/o4-mini) ---"
  echo "$CODEX_OUTPUT"
fi

echo ""
echo "================================================================"
echo "  Triage findings above before committing."
echo "  Critical/Important: fix before merge."
echo "  Minor: fix inline, card, or skip with justification."
echo "================================================================"

exit 0
