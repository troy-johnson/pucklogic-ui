---
name: sync
description: Produce a mission briefing from current project state. Run at the start of any session or any time context feels stale. Reads SESSION_STATE.md, git status, open PRs, and Notion ready-for-dev tickets, then outputs a single grounding table.
---

# /sync — Session Briefing

Produce a mission briefing. Do not start any implementation work until this is complete.

## Steps

Run all reads in parallel:

1. **Read `.claude/SESSION_STATE.md`** — current state pointer (phase, branch, PR, focus, next steps)
2. **`git branch --show-current`** — confirm active branch
3. **`git status --short`** — any uncommitted changes
4. **`gh pr list --state open`** — open PRs on this repo
5. **Fetch Notion "In Progress" and "Ready for Dev" tickets** via `mcp__claude_ai_Notion__notion-fetch`

## Output

Present a single briefing table, then stop and wait for the user to confirm direction:

```
## Mission Briefing — <date>

**Two-Axis: [Tier X | Scope: Y]** — fill in after reviewing SESSION_STATE and next action (Tier 1/2/3 per risk; Scope: Small/Medium/Large per files/sessions). If Tier 3 and Scope is Small, append: ⚠️ HIGH PRECISION REQUIRED: Small change, critical impact.

| Field | Value |
|---|---|
| Active Phase | |
| Active Branch | |
| Uncommitted Changes | |
| Open PRs | |
| SESSION_STATE says | |
| Notion In Progress | |
| Notion Ready for Dev | |

### Conflicts or drift detected
<list any discrepancies between SESSION_STATE.md, git state, and Notion — e.g. SESSION_STATE says branch X but git is on branch Y>

### Recommended next action
<one sentence — what should we work on based on the above>
```

Ask: "Does this look right? What would you like to work on?"

## Notes
- If `.claude/SESSION_STATE.md` does not exist, say so explicitly — it means the previous session ended without a handoff write
- If git branch is `main` and SESSION_STATE.md shows a feature branch, flag as a conflict
- Do not infer or fill in missing fields — leave them blank and note what's missing
