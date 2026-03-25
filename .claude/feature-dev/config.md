# Feature Dev Config — PuckLogic

## Stack
Python/FastAPI backend, pytest, Supabase PostgreSQL, Next.js frontend, shadcn/ui, Tailwind, Zustand, SWR.

## Commands
- **Lint**: `ruff check . && ruff format .`
- **Test**: `pytest`
- **Smoke tests**: `pytest tests/smoke/`
- **Frontend dev server**: `cd apps/web && pnpm dev`

## Directories
- **Frontend**: `apps/web/`
- **Backend**: `apps/api/`
- **Migrations**: `supabase/migrations/`
- **Specs**: `docs/superpowers/specs/`
- **Plans**: `docs/superpowers/plans/`

## Migration verification
`supabase db reset`

## CLAUDE.md files (update on sync only when a durable rule changed)
- `CLAUDE.md`
- `apps/api/CLAUDE.md`

## Agents
- **UI agent**: enabled for any PR touching `apps/web/`
  Prompt: `.claude/feature-dev/prompts/ui-review.md`
- **Security agent**: enabled, Tier 3 only
  Prompt: `.claude/feature-dev/prompts/security-review.md`
- **Browser checker**: not yet configured (future: agent-browser against `pnpm dev`)

## Plan review prompts
- Gemini: `.claude/feature-dev/prompts/plan-review-gemini.md`
- Codex: `.claude/feature-dev/prompts/plan-review-codex.md`

## Notion
- Task board in use: yes
- MCP tool: `mcp__claude_ai_Notion__notion-fetch`

## Serena
- In use: yes (local/Remote Control sessions only)
