# PuckLogic Implementation Review (Revised)

**Reviewer:** Gemini
**Date:** March 11, 2026

## 1. Overall Assessment

The PuckLogic project is well-documented, with a sound architecture and a logical phased rollout. However, a detailed cross-analysis of all documentation reveals **critical inconsistencies** across database schemas, API contracts, and security models. These issues of "documentation drift" are significant enough to block implementation and must be resolved before proceeding.

This revised review prioritizes these findings by severity and provides a concrete action plan.

---

## 2. Critical Findings

### Finding 1: Inconsistent API and Schema Definitions
The project's documentation contains numerous conflicting definitions for the same resources, making it impossible to implement with confidence. This suggests a systemic "documentation drift" problem.

**API Contract Conflicts:**

| Resource | Conflicting Docs | Conflict Description |
|---|---|---|
| Rankings | `claude-code-reference.md` vs. `phase-2-*` docs | `GET /api/rankings` vs. `POST /api/rankings/compute` |
| Trends | `claude-code-reference.md` vs. `phase-3-*` docs | Player-specific routes vs. a single list endpoint |
| Draft Sessions | `claude-code-reference.md` vs. `phase-4-backend.md` | `POST /api/draft/session` vs. `POST /api/draft/create-session` |

**Database Schema Conflicts:**

| Table / Column | Conflicting Docs | Conflict Description |
|---|---|---|
| `player_rankings.source` | `phase-1-backend.md` vs. `claude-code-reference.md` | `source TEXT` vs. `source_id UUID` (Foreign Key) |
| `user_kits` model | `phase-1-backend.md` vs. `pucklogic_architecture_v2.md` | Simple model vs. a complex one with `session_token` and normalized scoring configs. |
| `player_trends.shap` | `phase-1-backend.md` vs. `phase-3-backend.md` | `shap_json` vs. `shap_top3` |
| Projections Storage | `claude-code-reference.md` vs. `phase-3-backend.md` | `projected_stats JSONB` inline vs. a separate `player_projections` table. |

**Why this matters:** Different developers or agents working from these documents will build incompatible systems, leading to significant integration failures and rework.

### Finding 2: Insecure Extension Authentication and Session Handoff
The current plan for authenticating the browser extension and its WebSocket contains multiple security risks.

1.  **WebSocket Authentication:** The plan specifies passing the long-lived Supabase JWT as a URL query parameter. This is risky, as URLs are frequently logged by servers and can be exposed in browser history.
2.  **Web-to-Extension Communication:** The plan uses `window.postMessage` to send the session ID and WebSocket URL from the web app to the content script. This is an untrusted boundary. The current design does not specify validation of the message origin or payload, leaving it vulnerable to spoofing.

**Why this matters:** This creates an insecure channel for initializing the paid draft monitor, potentially allowing for session hijacking or unauthorized access.

### Finding 3: Ambiguous Security Enforcement Model
The documentation is unclear on whether Row Level Security (RLS) or the FastAPI application layer is the primary security boundary. The backend is configured with the `SUPABASE_SERVICE_ROLE_KEY`, which bypasses RLS. If the API layer is the true enforcer, every single endpoint that handles user-owned data must have explicit, tested authorization checks. This is not clearly stated or enforced.

**Why this matters:** An ambiguous security model is a common source of vulnerabilities. Without a clear contract, developers may incorrectly assume RLS is protecting data when it is actually being bypassed.

---

## 3. High-Impact Gaps

### Finding 4: Undefined Anonymous User Implementation
The architecture documents state that anonymous (pre-signup) users should be able to create and save draft kits. However, the phased implementation plans for the frontend and backend do not include this functionality. The login-protected `/dashboard` and owner-only RLS policies directly contradict the anonymous user requirement.

**Why this matters:** This is a core user journey that is architecturally required but has no implementation path. The project must either fully design this flow or formally move it to a post-v1 release.

### Finding 5: Missing Operational Plan for Data Ingestion
The ML model's success depends on a large historical dataset and a process for resolving data inconsistencies.
- **Historical Backfill:** The plan lacks a strategy for the initial, one-time bulk ingestion of 10+ years of data.
- **Player Matching:** The manual review process for unmatched players is mentioned but not designed. It is unclear who performs this review or how.

**Why this matters:** ML projects often fail due to data operations, not model code. These gaps represent significant, unscheduled work that is critical for the project's success.

---

## 4. Recommended Actions

### Priority 1: Blockers
1.  **Establish Canonical Contracts:** Freeze and publish a single, authoritative document for the **Database Schema** and another for the **API/WebSocket Contracts**. Deprecate or update all other documents to reference these sources of truth.
2.  **Redesign Extension Authentication:**
    *   Replace the JWT query parameter with a **short-lived, single-use ticket system** for WebSocket authentication. The extension should acquire this ticket from an authenticated REST endpoint.
    *   Define a secure contract for the `postMessage` bridge, including strict origin and schema validation.
3.  **Clarify the Security Model:** Explicitly state whether RLS or the API application layer is responsible for enforcement on a per-table/per-endpoint basis. Document and test all API-layer ownership checks.

### Priority 2: High-Impact Gaps
4.  **Decide on Anonymous User Flow:** Either fully design the anonymous kit creation, persistence, and migration flow for v1, or formally move it to the post-launch backlog and update all documentation accordingly.
5.  **Create a Data Operations Plan:** Schedule and design the tasks for the historical data backfill and the player alias review/curation workflow.

### Priority 3: Quality and Feature Improvements
6.  **Formalize E2E Testing:** Add an end-to-end testing strategy to the plan to validate the complete draft monitor flow, from web app payment to extension suggestions.
7.  **Address Feature Gaps:** For post-v1.0, begin planning for significant missing features like Goaltender support, Mock Drafts, and Keeper/Auction league tools.

---

## 5. Clarifying Questions

1.  **Player Matching:** What is the planned UI or process for the "manual review" of unmatched players?
2.  **Roto League Scoring:** For v1.0, will users be able to apply custom weights to the Z-scored categories?
3.  **Historical Data Backfill:** What is the strategy and timeline for the initial bulk data ingestion?
4.  **Anonymous Kit Cleanup:** What is the intended mechanism to trigger the 7-day cleanup of anonymous `user_kits`?
5.  **Goaltender Schema:** How will goalie-specific stats be incorporated into the database schema in future versions?
