# PuckLogic Phase 2 — Backend Implementation

## Aggregation Dashboard — Rankings Engine, Cache, Celery, Exports, Stripe

**Timeline:** May – June 2026 (Phase 2)
**Target Release:** v1.0 (September 2026)
**Reference:** `pucklogic_architecture.docx`

---

## Overview

Phase 2 backend builds the **core rankings engine** that powers the aggregation dashboard. It introduces the weighted composite rankings algorithm, a Redis cache layer (Upstash, 6h TTL), Celery background jobs for scraper orchestration, two new scrapers (Natural Stat Trick, Dobber Hockey), the Stripe webhook handler, and PDF/Excel export generation.

**Deliverables:**
1. ✅ Rankings computation endpoint (`POST /api/rankings/compute`)
2. ✅ Redis cache layer (Upstash, 6h TTL, cache-aside pattern)
3. ✅ Celery + Redis broker for background scraper jobs
4. ✅ Additional scrapers: Natural Stat Trick (HTML, BeautifulSoup), Dobber Hockey (Playwright), Elite Prospects
5. ✅ Stripe webhook handler → `subscriptions` table upsert
6. ✅ PDF export (WeasyPrint) and Excel export (openpyxl)
7. ✅ `GET /api/exports/generate` endpoint
8. ✅ Test coverage (pytest, mocked Redis/Stripe/scrapers)

---

## 1. Rankings Algorithm

### 1.1 Overview

The rankings engine converts per-source rank lists into a single composite ranking. The algorithm is league-format-aware: it outputs fantasy points + VORP for points leagues, and summed Z-scores for roto leagues.

**Location:** `apps/api/src/services/rankings.py`

**Algorithm steps:**
1. Fetch per-source rankings from `player_rankings` for the requested season
2. Normalize each source's ranks to a 0–1 score: `score = 1 - (rank - 1) / (max_rank - 1)`
3. Apply user-supplied weights (`weights` JSON from `user_kits`): `weighted_score = Σ (weight_i × score_i)` for each source
4. If a source is missing for a player, redistribute that source's weight proportionally across available sources (graceful degradation)
5. For **points leagues**: multiply weighted scores by user `scoring_settings` to get fantasy points, then compute VORP
6. For **roto leagues**: compute Z-score per scoring category across the player pool, sum Z-scores for final rank
7. Sort descending by final score / fantasy points
8. Cache result in Redis with key `rankings:{user_kit_id}:{season}` and 6h TTL

### 1.2 Service Class

```python
class RankingsService:
    def __init__(self, redis: Redis, supabase: Client):
        self.redis = redis
        self.supabase = supabase

    async def compute(
        self,
        user_kit_id: str,
        season: str,
        league_format: str,  # 'points' | 'roto' | 'head_to_head'
        scoring_settings: dict,
    ) -> list[RankedPlayer]:
        cache_key = f"rankings:{user_kit_id}:{season}"
        cached = await self.cache.get(cache_key)
        if cached:
            return cached

        raw = await self._fetch_rankings(season)
        normalized = self._normalize_ranks(raw)
        weights = await self._fetch_weights(user_kit_id)
        scored = self._apply_weights(normalized, weights)

        if league_format == "roto":
            ranked = self._compute_roto(scored, scoring_settings)
        else:
            ranked = self._compute_fantasy_pts(scored, scoring_settings)
            ranked = self._compute_vorp(ranked)

        ranked.sort(key=lambda p: p.final_score, reverse=True)
        await self.cache.set(cache_key, ranked)
        return ranked

    def _normalize_ranks(self, rankings: list[PlayerRanking]) -> dict[str, float]:
        """Normalize per-source ranks to 0–1 scores."""
        by_source: dict[str, list[PlayerRanking]] = {}
        for r in rankings:
            by_source.setdefault(r.source, []).append(r)

        normalized = {}
        for source, source_rankings in by_source.items():
            max_rank = max(r.rank for r in source_rankings)
            for r in source_rankings:
                score = 1 - (r.rank - 1) / (max_rank - 1) if max_rank > 1 else 1.0
                normalized.setdefault(r.player_id, {})[source] = score

        return normalized

    def _apply_weights(
        self,
        scores: dict[str, dict[str, float]],
        weights: dict[str, float],
    ) -> dict[str, float]:
        """Weighted average with graceful degradation for missing sources."""
        result = {}
        for player_id, source_scores in scores.items():
            available = {s: w for s, w in weights.items() if s in source_scores}
            total_weight = sum(available.values())
            if total_weight == 0:
                result[player_id] = 0.0
                continue
            weighted_sum = sum(
                source_scores[s] * (w / total_weight)
                for s, w in available.items()
            )
            result[player_id] = weighted_sum
        return result

    def _compute_vorp(self, players: list[RankedPlayer]) -> list[RankedPlayer]:
        """Value Over Replacement Player.
        Replacement level: Forward rank 150, Defenseman rank 60.
        """
        replacement_pts = {
            "F": self._replacement_fantasy_pts(players, position="F", rank=150),
            "D": self._replacement_fantasy_pts(players, position="D", rank=60),
            "G": self._replacement_fantasy_pts(players, position="G", rank=30),
        }
        for p in players:
            pos_group = "F" if p.position in ("C", "LW", "RW") else p.position
            p.vorp = p.fantasy_pts - replacement_pts.get(pos_group, 0)
        return players

    def _compute_roto(
        self,
        scored: dict[str, float],
        scoring_settings: dict,
    ) -> list[RankedPlayer]:
        """Z-score per category across player pool, sum for roto rank."""
        ...
```

### 1.3 API Endpoint

```
POST /api/rankings/compute
Authorization: Bearer <supabase_jwt>
Content-Type: application/json

Body:
{
  "user_kit_id": "uuid",
  "season": "2024-25",
  "force_refresh": false   // bypass cache and recompute
}

Response 200:
{
  "players": [RankedPlayer],
  "cached": true,
  "computed_at": "2026-06-01T12:00:00Z"
}
```

**Location:** `apps/api/src/routers/rankings.py`

```python
@router.post("/rankings/compute")
async def compute_rankings(
    body: RankingsComputeRequest,
    current_user: User = Depends(get_current_user),
    service: RankingsService = Depends(get_rankings_service),
) -> RankingsComputeResponse:
    kit = await get_user_kit(body.user_kit_id, current_user.id)
    if body.force_refresh:
        await service.cache.invalidate(f"rankings:{body.user_kit_id}:{body.season}")

    players = await service.compute(
        user_kit_id=body.user_kit_id,
        season=body.season,
        league_format=kit.league_format,
        scoring_settings=kit.scoring_settings,
    )
    return RankingsComputeResponse(
        players=players,
        cached=not body.force_refresh,
        computed_at=datetime.utcnow().isoformat(),
    )
```

### 1.4 Data Models

```python
from pydantic import BaseModel

class RankedPlayer(BaseModel):
    player_id: str
    name: str
    team: str
    position: str
    composite_rank: int
    composite_score: float
    fantasy_pts: float
    vorp: float
    source_ranks: dict[str, int]   # { "dobber": 12, "nhl_com": 14, ... }

class RankingsComputeRequest(BaseModel):
    user_kit_id: str
    season: str
    force_refresh: bool = False

class RankingsComputeResponse(BaseModel):
    players: list[RankedPlayer]
    cached: bool
    computed_at: str
```

---

## 2. Redis Cache Layer

### 2.1 Cache-Aside Pattern

**Location:** `apps/api/src/cache/redis.py`

- Client: `upstash_redis` Python SDK
- Pattern: cache-aside (check cache → miss → compute → store → return)
- TTL: 21600 seconds (6 hours)
- Key format: `rankings:{user_kit_id}:{season}`
- On `force_refresh=true`: delete key before compute
- Serialization: `json.dumps` / `json.loads` (safe text-based format)

```python
from upstash_redis import Redis
import json

class RankingsCache:
    TTL = 21600  # 6 hours in seconds

    def __init__(self, redis: Redis):
        self.redis = redis

    async def get(self, key: str) -> list[dict] | None:
        raw = await self.redis.get(key)
        if raw is None:
            return None
        return json.loads(raw)

    async def set(self, key: str, data: list[dict]) -> None:
        serialized = json.dumps([p.model_dump() for p in data])
        await self.redis.set(key, serialized, ex=self.TTL)

    async def invalidate(self, key: str) -> None:
        await self.redis.delete(key)
```

### 2.2 Configuration

```python
# apps/api/src/config.py
class Settings(BaseSettings):
    UPSTASH_REDIS_REST_URL: str
    UPSTASH_REDIS_REST_TOKEN: str

# apps/api/src/dependencies.py
def get_redis() -> Redis:
    return Redis(
        url=settings.UPSTASH_REDIS_REST_URL,
        token=settings.UPSTASH_REDIS_REST_TOKEN,
    )

def get_rankings_cache(redis: Redis = Depends(get_redis)) -> RankingsCache:
    return RankingsCache(redis)
```

### 2.3 Cache Key Design

| Key | TTL | Invalidation trigger |
|-----|-----|----------------------|
| `rankings:{user_kit_id}:{season}` | 6h | `force_refresh=true` or weight change |
| `exports:{user_id}:{format}:{kit_id}` | 1h | Generated on demand |

---

## 3. Celery Background Jobs

### 3.1 Celery Application Factory

**Location:** `apps/api/src/jobs/celery_app.py`

```python
from celery import Celery
from celery.schedules import crontab
from src.config import settings

app = Celery(
    "pucklogic",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["src.jobs.tasks.scrape"],
)

app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)

app.conf.beat_schedule = {
    "daily-scrape-nhl": {
        "task": "src.jobs.tasks.scrape.run_nhl_scrape",
        "schedule": crontab(hour=5, minute=0),
        "args": ("2024-25",),
    },
    "daily-scrape-nst": {
        "task": "src.jobs.tasks.scrape.run_nst_scrape",
        "schedule": crontab(hour=5, minute=30),
        "args": ("2024-25",),
    },
    "weekly-scrape-dobber": {
        "task": "src.jobs.tasks.scrape.run_dobber_scrape",
        "schedule": crontab(hour=6, minute=0, day_of_week=1),  # Monday
        "args": ("2024-25",),
    },
}
```

### 3.2 Scraper Tasks

**Location:** `apps/api/src/jobs/tasks/scrape.py`

```python
from celery import Task
from src.jobs.celery_app import app
from src.scrapers import nhl, natural_stat_trick, dobber, elite_prospects
import logging

logger = logging.getLogger(__name__)

@app.task(bind=True, max_retries=3, default_retry_delay=60)
def run_daily_scrape(self: Task, source: str, season: str) -> dict:
    """Dispatcher: routes to the correct scraper by source name.
    Triggered by GitHub Actions cron or Celery beat.
    """
    scrapers = {
        "nhl_com": run_nhl_scrape,
        "natural_stat_trick": run_nst_scrape,
        "dobber": run_dobber_scrape,
        "elite_prospects": run_ep_scrape,
    }
    try:
        task_fn = scrapers[source]
        return task_fn.delay(season)
    except KeyError:
        raise ValueError(f"Unknown scraper source: {source}")
    except Exception as exc:
        logger.exception("Scraper task failed for source=%s", source)
        raise self.retry(exc=exc)

@app.task(bind=True, max_retries=3, default_retry_delay=60)
def run_nhl_scrape(self: Task, season: str) -> dict:
    """NHL.com official API scraper (Phase 1 scraper, triggered by Celery)."""
    try:
        result = nhl.scrape(season)
        return {"source": "nhl_com", "players_scraped": result.count}
    except Exception as exc:
        raise self.retry(exc=exc)

@app.task(bind=True, max_retries=3, default_retry_delay=60)
def run_nst_scrape(self: Task, season: str) -> dict:
    """Natural Stat Trick HTML scraper (BeautifulSoup)."""
    try:
        result = natural_stat_trick.scrape(season)
        return {"source": "natural_stat_trick", "players_scraped": result.count}
    except Exception as exc:
        raise self.retry(exc=exc)

@app.task(bind=True, max_retries=3, default_retry_delay=120)
def run_dobber_scrape(self: Task, season: str) -> dict:
    """Dobber Hockey scraper (Playwright for JS-rendered pages)."""
    try:
        result = dobber.scrape(season)
        return {"source": "dobber", "players_scraped": result.count}
    except Exception as exc:
        raise self.retry(exc=exc)

@app.task(bind=True, max_retries=3, default_retry_delay=60)
def run_ep_scrape(self: Task, season: str) -> dict:
    """Elite Prospects HTML scraper."""
    try:
        result = elite_prospects.scrape(season)
        return {"source": "elite_prospects", "players_scraped": result.count}
    except Exception as exc:
        raise self.retry(exc=exc)
```

---

## 4. New Scrapers

### 4.1 Natural Stat Trick

**Location:** `apps/api/src/scrapers/natural_stat_trick.py`

- Method: `httpx` + `BeautifulSoup` (HTML table parsing)
- Target: `https://naturalstattrick.com/playerteams.php?sit=5v5`
- Respects `robots.txt`; 3-second delay between paginated requests
- Extracts: CF%, SCF%, xGF%, HDCF%, HDGF%, on-ice Corsi, on-ice Fenwick, on-ice shots for/against

```python
import httpx
import time
from bs4 import BeautifulSoup
from src.models import PlayerStats
from src.config import settings

NST_BASE_URL = "https://naturalstattrick.com"
NST_PLAYER_URL = f"{NST_BASE_URL}/playerteams.php"
REQUEST_DELAY_SECONDS = 3

class NaturalStatTrickScraper:
    def __init__(self):
        self.client = httpx.Client(
            headers={"User-Agent": settings.SCRAPER_USER_AGENT},
            timeout=30,
        )

    def scrape(self, season: str) -> list[PlayerStats]:
        """Scrape 5v5, PP, and SH situations and merge into PlayerStats."""
        results = []
        for sit in ("5v5", "pp", "sh"):
            params = {"sit": sit, "season": season, "score": "all", "lines": "individual"}
            time.sleep(REQUEST_DELAY_SECONDS)
            response = self.client.get(NST_PLAYER_URL, params=params)
            response.raise_for_status()
            rows = self._parse_table(response.text)
            results.extend(rows)
        return self._merge_situations(results)

    def _parse_table(self, html: str) -> list[dict]:
        soup = BeautifulSoup(html, "lxml")
        table = soup.find("table", id="players")
        if not table:
            raise ValueError("Player table not found in NST response")
        headers = [th.text.strip() for th in table.find("thead").find_all("th")]
        rows = []
        for tr in table.find("tbody").find_all("tr"):
            cells = [td.text.strip() for td in tr.find_all("td")]
            rows.append(dict(zip(headers, cells)))
        return rows

    def _merge_situations(self, rows: list[dict]) -> list[PlayerStats]:
        """Deduplicate by player_id and merge 5v5 / PP / SH columns."""
        ...
```

### 4.2 Dobber Hockey

**Location:** `apps/api/src/scrapers/dobber.py`

- Method: Playwright (headless Chromium) for JS-rendered rankings page
- Target: Dobber Hockey top-300 rankings
- Extracts: overall rank, positional rank, projected points, tier label
- Fallback: static HTML parse if JS rendering is not required (checked on each run)
- `robots.txt` respected; rate-limited to one page load per 5 seconds

```python
from playwright.sync_api import sync_playwright, Page
from src.models import PlayerRanking
import time

DOBBER_RANKINGS_URL = "https://dobberhockey.com/hockey-tools/rankings/"
PAGE_LOAD_DELAY_SECONDS = 5

class DobberScraper:
    def scrape(self, season: str) -> list[PlayerRanking]:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            time.sleep(PAGE_LOAD_DELAY_SECONDS)
            page.goto(DOBBER_RANKINGS_URL, wait_until="networkidle")
            rankings = self._extract_rankings(page, season)
            browser.close()
        return rankings

    def _extract_rankings(self, page: Page, season: str) -> list[PlayerRanking]:
        """Extract ranking rows from the rendered DOM."""
        rows = page.query_selector_all("table.rankings-table tbody tr")
        result = []
        for i, row in enumerate(rows, start=1):
            cells = row.query_selector_all("td")
            if len(cells) < 4:
                continue
            result.append(PlayerRanking(
                source="dobber",
                rank=i,
                player_name=cells[1].inner_text().strip(),
                position=cells[2].inner_text().strip(),
                projected_points=float(cells[3].inner_text().strip() or 0),
                season=season,
            ))
        return result
```

### 4.3 Elite Prospects

**Location:** `apps/api/src/scrapers/elite_prospects.py`

- Method: `httpx` + `BeautifulSoup` (or EP public API if accessible)
- Target: Elite Prospects top skaters by fantasy-relevant stats
- Extracts: overall rank, GP, G, A, PTS, position, team, age
- 3-second delay between paginated requests; `robots.txt` respected

---

## 5. Stripe Webhook Handler

### 5.1 Webhook Endpoint

**Location:** `apps/api/src/routers/stripe.py`

```python
import stripe
from fastapi import APIRouter, Request, HTTPException
from src.config import settings
from src.repositories.subscriptions import SubscriptionRepository

router = APIRouter(prefix="/webhooks")

@router.post("/stripe")
async def stripe_webhook(
    request: Request,
    sub_repo: SubscriptionRepository = Depends(get_sub_repo),
) -> dict:
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid Stripe signature")

    if event.type == "checkout.session.completed":
        await handle_checkout_completed(event.data.object, sub_repo)
    elif event.type == "customer.subscription.updated":
        await handle_subscription_change(event.data.object, sub_repo)
    elif event.type == "customer.subscription.deleted":
        await handle_subscription_cancelled(event.data.object, sub_repo)

    return {"received": True}

async def handle_checkout_completed(session: dict, repo: SubscriptionRepository) -> None:
    """Upsert subscription row after successful Stripe Checkout."""
    await repo.upsert(
        stripe_customer_id=session["customer"],
        stripe_subscription_id=session["subscription"],
        plan="pro",
        status="active",
        expires_at=None,  # pulled from subscription object
    )

async def handle_subscription_change(sub: dict, repo: SubscriptionRepository) -> None:
    await repo.upsert(
        stripe_customer_id=sub["customer"],
        stripe_subscription_id=sub["id"],
        plan=sub["items"]["data"][0]["price"]["lookup_key"],
        status=sub["status"],
        expires_at=sub.get("current_period_end"),
    )

async def handle_subscription_cancelled(sub: dict, repo: SubscriptionRepository) -> None:
    await repo.upsert(
        stripe_customer_id=sub["customer"],
        stripe_subscription_id=sub["id"],
        plan="free",
        status="cancelled",
        expires_at=sub.get("canceled_at"),
    )
```

### 5.2 Subscriptions Repository

**Location:** `apps/api/src/repositories/subscriptions.py`

```python
class SubscriptionRepository:
    def __init__(self, supabase: Client):
        self.supabase = supabase

    async def upsert(
        self,
        stripe_customer_id: str,
        stripe_subscription_id: str,
        plan: str,
        status: str,
        expires_at: int | None,
    ) -> None:
        """Upsert into the subscriptions table keyed on stripe_customer_id."""
        data = {
            "stripe_customer_id": stripe_customer_id,
            "stripe_subscription_id": stripe_subscription_id,
            "plan": plan,
            "status": status,
            "expires_at": expires_at,
            "updated_at": "now()",
        }
        self.supabase.table("subscriptions").upsert(
            data, on_conflict="stripe_customer_id"
        ).execute()
```

### 5.3 Stripe Environment Variables

| Variable | Description |
|----------|-------------|
| `STRIPE_SECRET_KEY` | Stripe API secret key (`sk_live_...`) |
| `STRIPE_WEBHOOK_SECRET` | Webhook signing secret (`whsec_...`) |
| `STRIPE_PRO_PRICE_ID` | Price ID for the Pro plan (`price_...`) |

---

## 6. Export Service

### 6.1 Service Class

**Location:** `apps/api/src/services/exports.py`

```python
from weasyprint import HTML
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from jinja2 import Environment, PackageLoader
from src.models import RankedPlayer

class ExportService:
    def __init__(self, supabase: Client, jinja_env: Environment):
        self.supabase = supabase
        self.jinja = jinja_env

    async def generate_pdf(
        self, rankings: list[RankedPlayer], kit_name: str
    ) -> bytes:
        """Render rankings to HTML via Jinja2 template → WeasyPrint → PDF bytes."""
        template = self.jinja.get_template("rankings_export.html")
        html_str = template.render(
            players=rankings,
            kit_name=kit_name,
            generated_at=datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
        )
        pdf_bytes = HTML(string=html_str).write_pdf()
        return pdf_bytes

    async def generate_excel(self, rankings: list[RankedPlayer]) -> bytes:
        """openpyxl workbook with player rankings + per-source rank columns."""
        wb = Workbook()
        ws = wb.active
        ws.title = "PuckLogic Rankings"

        # Header row
        headers = [
            "Rank", "Player", "Team", "Pos",
            "Fantasy Pts", "VORP", "Composite Score",
        ]
        # Append per-source columns dynamically
        if rankings:
            headers += [f"{src} Rank" for src in rankings[0].source_ranks.keys()]

        header_fill = PatternFill(start_color="1A3A5C", end_color="1A3A5C", fill_type="solid")
        header_font = Font(color="FFFFFF", bold=True)
        for col_idx, header in enumerate(headers, start=1):
            cell = ws.cell(row=1, column=col_idx, value=header)
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal="center")

        # Data rows
        for rank_idx, player in enumerate(rankings, start=1):
            row = [
                rank_idx,
                player.name,
                player.team,
                player.position,
                round(player.fantasy_pts, 1),
                round(player.vorp, 1),
                round(player.composite_score, 4),
            ]
            row += list(player.source_ranks.values())
            ws.append(row)

        # Auto-fit column widths
        for col in ws.columns:
            max_len = max(len(str(cell.value or "")) for cell in col)
            ws.column_dimensions[col[0].column_letter].width = max(12, max_len + 2)

        # Return as bytes
        from io import BytesIO
        buf = BytesIO()
        wb.save(buf)
        buf.seek(0)
        return buf.read()

    async def upload_to_storage(
        self, data: bytes, filename: str, user_id: str
    ) -> str:
        """Upload to Supabase Storage bucket 'exports', return 1h signed URL."""
        path = f"{user_id}/{filename}"
        self.supabase.storage.from_("exports").upload(
            path, data, file_options={"content-type": self._mime(filename)}
        )
        signed = self.supabase.storage.from_("exports").create_signed_url(
            path, expires_in=3600
        )
        return signed["signedURL"]

    def _mime(self, filename: str) -> str:
        return "application/pdf" if filename.endswith(".pdf") else (
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
```

### 6.2 Export API Endpoint

**Location:** `apps/api/src/routers/exports.py`

```
GET /api/exports/generate?format=pdf&user_kit_id=<uuid>&season=2024-25
Authorization: Bearer <supabase_jwt>   # Pro subscription required
```

```python
@router.get("/exports/generate")
async def generate_export(
    format: Literal["pdf", "xlsx"],
    user_kit_id: str,
    season: str,
    current_user: User = Depends(get_current_user),
    rankings_service: RankingsService = Depends(get_rankings_service),
    export_service: ExportService = Depends(get_export_service),
) -> ExportResponse:
    require_pro_subscription(current_user)

    players = await rankings_service.compute(
        user_kit_id=user_kit_id,
        season=season,
        league_format=current_user.default_league_format,
        scoring_settings=current_user.scoring_settings,
    )

    kit = await get_user_kit(user_kit_id)
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    filename = f"pucklogic_{kit.name}_{timestamp}.{format}"

    if format == "pdf":
        data = await export_service.generate_pdf(players, kit.name)
    else:
        data = await export_service.generate_excel(players)

    signed_url = await export_service.upload_to_storage(data, filename, current_user.id)

    # Record export job
    await record_export(current_user.id, format, "complete", signed_url)

    return ExportResponse(url=signed_url, filename=filename, expires_in=3600)
```

**Export flow:**
1. Verify Pro subscription (HTTP 403 for free users)
2. Compute rankings (uses cached result if available)
3. Generate PDF (WeasyPrint) or Excel (openpyxl)
4. Upload to Supabase Storage bucket `exports`
5. Insert row into `exports` table (`status = "complete"`, `storage_url`)
6. Return signed URL (expires 1h)

### 6.3 HTML Template for PDF

**Location:** `apps/api/src/templates/rankings_export.html`

Jinja2 template rendered by WeasyPrint. Includes:
- PuckLogic logo + kit name header
- Generation timestamp and season label
- Ranked player table with columns: Rank, Player, Team, Pos, Fantasy Pts, VORP, per-source ranks
- Print-optimized CSS (A4 portrait, 10pt font, alternating row shading)

---

## 7. Testing

### 7.1 Rankings Service Tests

**Location:** `tests/services/test_rankings.py`

| Test case | Assertion |
|-----------|-----------|
| Normalization with 10 players | Top-ranked player scores 1.0; last-ranked scores 0.0 |
| Equal weights, two sources | Composite score equals mean of both normalized scores |
| Missing source for one player | Weight redistributed; player still ranked |
| VORP replacement level (F=150) | Player at rank 150 has VORP ≈ 0 |
| Roto Z-score | Player above mean has positive summed Z |
| Cache hit | DB not called; cached data returned |
| `force_refresh=true` | Cache invalidated; DB called |

```python
# tests/services/test_rankings.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from src.services.rankings import RankingsService

@pytest.fixture
def mock_redis():
    redis = MagicMock()
    redis.get = AsyncMock(return_value=None)
    redis.set = AsyncMock()
    redis.delete = AsyncMock()
    return redis

@pytest.fixture
def mock_supabase():
    return MagicMock()

def test_normalize_ranks_top_player_scores_one(mock_redis, mock_supabase):
    service = RankingsService(redis=mock_redis, supabase=mock_supabase)
    rankings = [
        MagicMock(player_id="p1", source="nhl_com", rank=1),
        MagicMock(player_id="p2", source="nhl_com", rank=2),
        MagicMock(player_id="p3", source="nhl_com", rank=3),
    ]
    normalized = service._normalize_ranks(rankings)
    assert normalized["p1"]["nhl_com"] == pytest.approx(1.0)
    assert normalized["p3"]["nhl_com"] == pytest.approx(0.0)

def test_apply_weights_missing_source_redistributes(mock_redis, mock_supabase):
    service = RankingsService(redis=mock_redis, supabase=mock_supabase)
    scores = {
        "p1": {"nhl_com": 0.9, "dobber": 0.8},
        "p2": {"nhl_com": 0.7},  # dobber missing for p2
    }
    weights = {"nhl_com": 0.5, "dobber": 0.5}
    result = service._apply_weights(scores, weights)
    # p2 only has nhl_com; full weight applied to available source
    assert result["p2"] == pytest.approx(0.7)
```

### 7.2 Cache Tests

**Location:** `tests/cache/test_redis.py`

```python
import pytest
from unittest.mock import AsyncMock, MagicMock
from src.cache.redis import RankingsCache

@pytest.fixture
def mock_upstash():
    redis = MagicMock()
    redis.get = AsyncMock(return_value=None)
    redis.set = AsyncMock()
    redis.delete = AsyncMock()
    return redis

async def test_cache_miss_returns_none(mock_upstash):
    cache = RankingsCache(mock_upstash)
    result = await cache.get("rankings:kit-1:2024-25")
    assert result is None
    mock_upstash.get.assert_called_once_with("rankings:kit-1:2024-25")

async def test_cache_set_uses_ttl(mock_upstash):
    cache = RankingsCache(mock_upstash)
    await cache.set("rankings:kit-1:2024-25", [])
    mock_upstash.set.assert_called_once()
    _, kwargs = mock_upstash.set.call_args
    assert kwargs.get("ex") == RankingsCache.TTL

async def test_cache_invalidate_deletes_key(mock_upstash):
    cache = RankingsCache(mock_upstash)
    await cache.invalidate("rankings:kit-1:2024-25")
    mock_upstash.delete.assert_called_once_with("rankings:kit-1:2024-25")
```

### 7.3 Stripe Webhook Tests

**Location:** `tests/routers/test_stripe.py`

```python
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from fastapi.testclient import TestClient
from src.main import app

client = TestClient(app)

def test_invalid_signature_returns_400():
    with patch("stripe.Webhook.construct_event", side_effect=stripe.error.SignatureVerificationError("bad", "sig")):
        response = client.post(
            "/webhooks/stripe",
            content=b"{}",
            headers={"stripe-signature": "bad_sig"},
        )
    assert response.status_code == 400

def test_checkout_completed_upserts_subscription():
    mock_event = MagicMock()
    mock_event.type = "checkout.session.completed"
    mock_event.data.object = {"customer": "cus_123", "subscription": "sub_456"}

    with patch("stripe.Webhook.construct_event", return_value=mock_event):
        with patch("src.routers.stripe.handle_checkout_completed", new_callable=AsyncMock) as mock_handler:
            response = client.post(
                "/webhooks/stripe",
                content=b"{}",
                headers={"stripe-signature": "valid_sig"},
            )
    assert response.status_code == 200
    mock_handler.assert_called_once()
```

### 7.4 Export Service Tests

**Location:** `tests/services/test_exports.py`

```python
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from src.services.exports import ExportService

@pytest.fixture
def mock_players():
    player = MagicMock()
    player.name = "Connor McDavid"
    player.team = "EDM"
    player.position = "C"
    player.fantasy_pts = 287.5
    player.vorp = 142.3
    player.composite_score = 0.9812
    player.source_ranks = {"nhl_com": 1, "dobber": 1}
    return [player]

async def test_generate_excel_returns_bytes(mock_players):
    service = ExportService(supabase=MagicMock(), jinja_env=MagicMock())
    result = await service.generate_excel(mock_players)
    assert isinstance(result, bytes)
    assert len(result) > 0

async def test_generate_pdf_calls_weasyprint(mock_players):
    mock_jinja = MagicMock()
    mock_jinja.get_template.return_value.render.return_value = "<html></html>"
    service = ExportService(supabase=MagicMock(), jinja_env=mock_jinja)

    with patch("src.services.exports.HTML") as mock_html:
        mock_html.return_value.write_pdf.return_value = b"%PDF-1.4"
        result = await service.generate_pdf(mock_players, kit_name="My Kit")

    assert result == b"%PDF-1.4"
    mock_html.assert_called_once()
```

### 7.5 Scraper Tests

**Location:** `tests/scrapers/test_nst.py`

```python
import pytest
from pathlib import Path
from src.scrapers.natural_stat_trick import NaturalStatTrickScraper

NST_FIXTURE = Path(__file__).parent / "fixtures" / "nst_playerteams_5v5.html"

def test_parse_table_extracts_correct_columns():
    scraper = NaturalStatTrickScraper()
    html = NST_FIXTURE.read_text()
    rows = scraper._parse_table(html)

    assert len(rows) > 0
    first = rows[0]
    assert "Player" in first
    assert "CF%" in first
    assert "xGF%" in first

def test_parse_table_raises_on_missing_table():
    scraper = NaturalStatTrickScraper()
    with pytest.raises(ValueError, match="Player table not found"):
        scraper._parse_table("<html><body>no table here</body></html>")
```

---

## 8. Deployment Checklist

- [ ] `UPSTASH_REDIS_REST_URL` and `UPSTASH_REDIS_REST_TOKEN` set in Railway/Fly.io env
- [ ] `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `STRIPE_PRO_PRICE_ID` set in env
- [ ] Stripe webhook endpoint registered in Stripe dashboard (`/webhooks/stripe`)
- [ ] Supabase Storage bucket `exports` created with appropriate RLS policies
- [ ] Celery worker and beat scheduler deployed alongside FastAPI
- [ ] GitHub Actions cron workflows confirmed active for daily scrapes
- [ ] `playwright install chromium` run in Dobber scraper environment
- [ ] WeasyPrint system dependencies (`libpango`, `libcairo`) installed in container
- [ ] All pytest tests passing with >85% coverage
- [ ] `robots.txt` verified for Natural Stat Trick and Elite Prospects before deployment

---

## 9. Performance Considerations

| Operation | Target | Strategy |
|-----------|--------|----------|
| Rankings compute (cold) | <3s | Supabase indexed queries + async fetch |
| Rankings compute (cached) | <100ms | Upstash Redis GET |
| PDF generation (500 players) | <10s | WeasyPrint async, run in thread pool |
| Excel generation (500 players) | <5s | openpyxl in-memory, no disk I/O |
| NST scrape (full table) | <60s | Paginated with 3s delays |
| Dobber scrape (Playwright) | <120s | Headless Chromium, network-idle wait |

---

## Appendix: Key Files

| File | Purpose |
|------|---------|
| `apps/api/src/services/rankings.py` | Core rankings algorithm (normalize → weight → VORP/roto) |
| `apps/api/src/services/exports.py` | PDF (WeasyPrint) and Excel (openpyxl) generation |
| `apps/api/src/cache/redis.py` | Upstash Redis cache-aside wrapper |
| `apps/api/src/routers/rankings.py` | `POST /api/rankings/compute` endpoint |
| `apps/api/src/routers/exports.py` | `GET /api/exports/generate` endpoint |
| `apps/api/src/routers/stripe.py` | `POST /webhooks/stripe` handler |
| `apps/api/src/scrapers/natural_stat_trick.py` | NST HTML scraper (httpx + BeautifulSoup) |
| `apps/api/src/scrapers/dobber.py` | Dobber scraper (Playwright headless Chromium) |
| `apps/api/src/scrapers/elite_prospects.py` | Elite Prospects HTML scraper |
| `apps/api/src/jobs/celery_app.py` | Celery application factory + beat schedule |
| `apps/api/src/jobs/tasks/scrape.py` | Celery scraper tasks (with retry logic) |
| `apps/api/src/repositories/subscriptions.py` | Supabase `subscriptions` table upsert |
| `apps/api/src/templates/rankings_export.html` | Jinja2 HTML template for PDF export |
| `apps/api/tests/services/test_rankings.py` | Rankings normalization, weighting, VORP tests |
| `apps/api/tests/services/test_exports.py` | PDF/Excel generation tests (mocked) |
| `apps/api/tests/cache/test_redis.py` | Cache hit/miss/TTL/invalidation tests |
| `apps/api/tests/routers/test_stripe.py` | Webhook signature validation and upsert tests |
| `apps/api/tests/scrapers/test_nst.py` | NST fixture HTML → parsed stats assertions |

---

*See also: `docs/phase-2-frontend.md` (dashboard UI implementation)*
