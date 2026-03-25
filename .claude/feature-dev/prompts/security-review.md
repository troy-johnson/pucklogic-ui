You are reviewing a pull request for the PuckLogic fantasy hockey draft kit (Python/FastAPI backend, Supabase PostgreSQL with RLS, Stripe billing, external scrapers).

Focus exclusively on security surface — not code style, not test coverage, not performance.

Review for:

1. **Supabase RLS bypass** — Any new SQL query or Supabase client call that uses the service-role key where the anon/user key should be used. New tables without RLS policies. Queries that could return rows belonging to other users if RLS is misconfigured or bypassed via a join. Policy conditions that reference auth.uid() but could be fooled by a crafted request.

2. **FastAPI auth gaps** — New routes missing Depends(get_current_user) or equivalent auth dependency. Endpoints that accept user-supplied IDs without verifying the requesting user owns that resource (IDOR risk). Routes that return data from multiple tenants without scoping to the authenticated user.

3. **Stripe security** — Webhook handlers missing signature verification (stripe.Webhook.construct_event with STRIPE_WEBHOOK_SECRET). Price/amount values read from client request body instead of fetched from Stripe server-side. Subscription status checked from a local cache that could be stale rather than from Stripe directly for billing-critical decisions.

4. **Secret exposure** — API keys, tokens, or credentials hardcoded or logged. Environment variables accessed in frontend code that should be server-only (NEXT_PUBLIC_ prefix on secrets). Service-role key used in client-side Supabase initialization.

5. **Scraper ethics and rate limiting** — New scrapers missing robots.txt compliance check. Missing rate limiting or exponential backoff on retry logic. User-agent string missing or deceptive. Scraper that could inadvertently trigger account bans or legal risk by ignoring ToS signals.

6. **Input validation** — New FastAPI endpoints missing Pydantic model validation on request bodies. Query parameters used directly in SQL without parameterization. File upload endpoints missing type/size validation.

7. **Data exposure in responses** — API responses that include fields the client doesn't need (e.g. password hashes, internal IDs, other users' data). Error responses that leak stack traces, SQL queries, or internal file paths to the client.

For each issue: severity (Critical/Important/Minor), file:line, description, suggested fix.
Critical = exploitable by an authenticated user or unauthenticated request with predictable input.
Be concise. Flag real issues only — do not invent problems.

The diff to review follows:
