# Phase 2 — Projection Aggregation Pipeline Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the rank-based aggregation engine with a stat-projection-based pipeline that ingests per-source projected counting stats, computes weighted averages, applies scoring configs, computes VORP, and returns fantasy-ready rankings.

**Architecture:** A new service layer (`services/projections.py`) handles all math as pure functions. A new repository (`repositories/projections.py`) fetches pre-joined DB rows. The existing `rankings` router is rewired to call the new pipeline. League profiles (new table + CRUD) provide VORP inputs. Exports are updated to render the new output shape.

**Tech Stack:** FastAPI, Supabase (PostgREST), Pydantic v2, openpyxl, WeasyPrint, pytest + MagicMock, SHA-256 cache keys via `hashlib`

**Spec:** `docs/superpowers/specs/2026-03-13-projection-aggregation-design.md`
**Backend reference:** `docs/backend-reference.md`

---

## Chunk 1: Schema Migration + BaseProjectionScraper

### Task 1: Migration 002 — new tables and column additions

**Files:**
- Create: `supabase/migrations/002_projection_aggregation.sql`

- [ ] **Step 1: Write migration 002**

```sql
-- supabase/migrations/002_projection_aggregation.sql
-- Phase 2: Projection aggregation pipeline schema additions.
-- Recreates player_projections with per-stat columns + source_id FK.
-- Adds schedule_scores, player_platform_positions, league_profiles.
-- Adds default_weight, is_paid, user_id columns to sources.
-- ---------------------------------------------------------------------------

-- ---------------------------------------------------------------------------
-- player_projections (recreate with correct schema)
-- Per-source projected counting stats. source_id FK makes the unique
-- constraint (player_id, source_id, season) rather than (player_id, season).
-- null stat = source did not project this stat (≠ zero).
-- ---------------------------------------------------------------------------
drop table if exists player_projections;

create table player_projections (
  id          uuid primary key default gen_random_uuid(),
  player_id   uuid not null references players (id) on delete cascade,
  source_id   uuid not null references sources (id) on delete cascade,
  season      text not null,
  -- skater stats (all nullable — null means not projected)
  g           integer,
  a           integer,
  plus_minus  integer,
  pim         integer,
  ppg         integer,
  ppa         integer,
  ppp         integer,
  shg         integer,
  sha         integer,
  shp         integer,
  sog         integer,
  fow         integer,
  fol         integer,
  hits        integer,
  blocks      integer,
  gp          integer,
  -- goalie stats (all nullable)
  gs          integer,
  w           integer,
  l           integer,
  ga          integer,
  sa          integer,
  sv          integer,
  sv_pct      float,
  so          integer,
  otl         integer,
  -- overflow for source-specific stats not in the fixed set
  extra_stats jsonb,
  updated_at  timestamptz not null default now(),
  unique (player_id, source_id, season)
);

create index if not exists player_projections_player_idx on player_projections (player_id);
create index if not exists player_projections_season_idx on player_projections (season);
create index if not exists player_projections_source_idx on player_projections (source_id);

alter table player_projections enable row level security;
-- Read access filtered through source visibility: system sources (user_id IS NULL)
-- or the requesting user's own custom sources. Spec §7.6.
create policy "Read through visible sources" on player_projections
  for select using (
    exists (
      select 1 from sources
      where sources.id = player_projections.source_id
        and (sources.user_id is null or sources.user_id = auth.uid())
    )
  );
-- Writes restricted to service role (trusted backend ingestion paths only)
create policy "Service write" on player_projections
  for insert with check (auth.role() = 'service_role');

-- ---------------------------------------------------------------------------
-- sources — RLS policies per spec §7.6
-- ---------------------------------------------------------------------------
-- SELECT: system sources + own custom sources
drop policy if exists "Public read" on sources;
create policy "Visible sources read" on sources
  for select using (user_id is null or user_id = auth.uid());
-- INSERT/UPDATE/DELETE: only own custom sources
create policy "Owner manage custom sources" on sources
  for all using (user_id = auth.uid());
-- System rows (user_id IS NULL) remain read-only from user context

-- ---------------------------------------------------------------------------
-- sources additions
-- ---------------------------------------------------------------------------
alter table sources add column if not exists default_weight float;
alter table sources add column if not exists is_paid boolean not null default false;
-- user_id references auth.users — set for user-uploaded custom sources, null for system sources
alter table sources add column if not exists user_id uuid references auth.users (id) on delete set null;

create index if not exists sources_user_idx on sources (user_id);

-- ---------------------------------------------------------------------------
-- schedule_scores
-- Off-night game counts per player per season.
-- "Off night" = a date where < 16 of 32 NHL teams play.
-- All stat columns are nullable: null = schedule not yet populated for that player.
-- ---------------------------------------------------------------------------
create table if not exists schedule_scores (
  player_id        uuid not null references players (id) on delete cascade,
  season           text not null,
  off_night_games  integer,              -- null until schedule ingestion runs
  total_games      integer,
  schedule_score   float,               -- min-max normalised 0–1; null until populated
  updated_at       timestamptz not null default now(),
  primary key (player_id, season)
);

create index if not exists schedule_scores_season_idx on schedule_scores (season);

alter table schedule_scores enable row level security;
create policy "Public read" on schedule_scores for select using (true);

-- ---------------------------------------------------------------------------
-- player_platform_positions
-- Platform-specific position eligibility — separate from players.position
-- (NHL.com canonical). Dual eligibility derived at query time.
-- ---------------------------------------------------------------------------
create table if not exists player_platform_positions (
  player_id  uuid not null references players (id) on delete cascade,
  platform   text not null,              -- 'espn', 'yahoo', 'fantrax'
  positions  text[] not null,            -- e.g. ['LW', 'RW']
  primary key (player_id, platform)
);

create index if not exists player_platform_positions_player_idx
  on player_platform_positions (player_id);
create index if not exists player_platform_positions_platform_idx
  on player_platform_positions (platform);

alter table player_platform_positions enable row level security;
create policy "Public read" on player_platform_positions for select using (true);

-- ---------------------------------------------------------------------------
-- league_profiles
-- Full league configuration needed to compute VORP.
-- ---------------------------------------------------------------------------
create table if not exists league_profiles (
  id                uuid primary key default gen_random_uuid(),
  user_id           uuid not null,
  name              text not null,
  platform          text not null check (platform in ('espn', 'yahoo', 'fantrax')),
  num_teams         integer not null check (num_teams > 0),
  roster_slots      jsonb not null,
  scoring_config_id uuid references scoring_configs (id),
  created_at        timestamptz not null default now()
);

create index if not exists league_profiles_user_idx on league_profiles (user_id);

alter table league_profiles enable row level security;
create policy "Owner only" on league_profiles for all using (auth.uid() = user_id);
```

- [ ] **Step 2: Verify migration file is syntactically valid (dry run)**

```bash
cd /path/to/project
# If you have psql / supabase CLI:
# supabase db reset --local   OR just review the SQL manually.
# At minimum: confirm no typos in table/column names against the spec.
grep -c "create table" supabase/migrations/002_projection_aggregation.sql
# Expected: 4  (player_projections, schedule_scores, player_platform_positions, league_profiles)
```

- [ ] **Step 3: Commit**

```bash
git add supabase/migrations/002_projection_aggregation.sql
git commit -m "feat(schema): add migration 002 — projection aggregation tables and source additions"
```

---

### Task 2: BaseProjectionScraper ABC

**Files:**
- Create: `apps/api/scrapers/base_projection.py`
- Create: `apps/api/tests/scrapers/test_base_projection.py`

- [ ] **Step 1: Write the failing test**

```python
# apps/api/tests/scrapers/test_base_projection.py
from __future__ import annotations

import pytest
from unittest.mock import MagicMock

from scrapers.base_projection import BaseProjectionScraper


class ConcreteProjectionScraper(BaseProjectionScraper):
    SOURCE_NAME = "test_source"
    DISPLAY_NAME = "Test Source"

    async def scrape(self, season: str, db: object) -> int:
        return 0


class TestBaseProjectionScraperContract:
    def test_source_name_required(self) -> None:
        scraper = ConcreteProjectionScraper()
        assert scraper.SOURCE_NAME == "test_source"

    def test_display_name_required(self) -> None:
        scraper = ConcreteProjectionScraper()
        assert scraper.DISPLAY_NAME == "Test Source"

    def test_missing_source_name_raises(self) -> None:
        with pytest.raises(TypeError):
            class BadScraper(BaseProjectionScraper):
                DISPLAY_NAME = "Bad"
                # SOURCE_NAME missing — abstract attr
            BadScraper()

    def test_missing_scrape_raises(self) -> None:
        with pytest.raises(TypeError):
            class BadScraper(BaseProjectionScraper):
                SOURCE_NAME = "x"
                DISPLAY_NAME = "X"
                # scrape() not implemented
            BadScraper()

    @pytest.mark.asyncio
    async def test_scrape_returns_int(self) -> None:
        scraper = ConcreteProjectionScraper()
        result = await scraper.scrape("2025-26", MagicMock())
        assert isinstance(result, int)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd apps/api && pytest tests/scrapers/test_base_projection.py -v
# Expected: FAIL — ModuleNotFoundError: No module named 'scrapers.base_projection'
```

- [ ] **Step 3: Write BaseProjectionScraper**

```python
# apps/api/scrapers/base_projection.py
"""
Abstract base class for projection-source scrapers.

Separate from BaseScraper (which writes to player_stats).
All projection scrapers — auto-scraped and user-uploaded — implement this ABC.
HTTP helpers (robots.txt, retry) are inherited from BaseScraper where needed;
import BaseScraper in your concrete class if you need network access.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseProjectionScraper(ABC):
    """Scrapes or parses a projection source and writes rows to player_projections.

    Class attributes that concrete scrapers MUST define:
        SOURCE_NAME   — machine key matching sources.name (e.g. "hashtag_hockey")
        DISPLAY_NAME  — human label (e.g. "Hashtag Hockey")
    """

    SOURCE_NAME: str
    DISPLAY_NAME: str

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        # Enforce class-level attributes at definition time so errors surface
        # immediately, not at instantiation. Skip check for abstract subclasses.
        if not getattr(cls, "__abstractmethods__", None):
            for attr in ("SOURCE_NAME", "DISPLAY_NAME"):
                if not hasattr(cls, attr) or isinstance(
                    getattr(cls, attr), property
                ):
                    raise TypeError(
                        f"{cls.__name__} must define class attribute {attr!r}"
                    )

    @abstractmethod
    async def scrape(self, season: str, db: Any) -> int:
        """Fetch projections, resolve player names, upsert to player_projections.

        Args:
            season: e.g. "2025-26"
            db:     Supabase Client (service role)

        Returns:
            Number of player_projections rows upserted.

        Contract:
            - Must check robots.txt before any HTTP requests (use BaseScraper helpers).
            - Unmatched player names: log to scraper_logs, skip row, never raise.
            - Null stat vs zero stat: null means not projected; do not coerce to 0.
        """
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd apps/api && pytest tests/scrapers/test_base_projection.py -v
# Expected: all pass
```

- [ ] **Step 5: Commit**

```bash
git add scrapers/base_projection.py tests/scrapers/test_base_projection.py
git commit -m "feat(scrapers): add BaseProjectionScraper ABC"
```

---

## Chunk 2: Schemas + Projection Repository

### Task 3: Update Pydantic schemas

**Files:**
- Modify: `apps/api/models/schemas.py`

Replace old ranking/export schemas with new projection-based shapes. Keep all unrelated schemas (SourceOut, Stripe, UserKit, ExportJobResponse) unchanged.

- [ ] **Step 1: Replace ranking and export schemas in schemas.py**

Replace from `class RankingsComputeRequest` through `class ExportRequest` with:

```python
# Add to existing pydantic import line in schemas.py:
#   from pydantic import BaseModel, Field, model_validator

# ---------------------------------------------------------------------------
# Rankings — projection-based pipeline
# ---------------------------------------------------------------------------

SKATER_STATS = [
    "g", "a", "plus_minus", "pim", "ppg", "ppa", "ppp",
    "shg", "sha", "shp", "sog", "fow", "fol", "hits", "blocks", "gp",
]
GOALIE_STATS = ["gs", "w", "l", "ga", "sa", "sv", "sv_pct", "so", "otl"]
ALL_PROJECTION_STATS = SKATER_STATS + GOALIE_STATS


class RankingsComputeRequest(BaseModel):
    season: str = Field(..., examples=["2025-26"])
    source_weights: dict[str, float] = Field(
        ...,
        description="Source name → weight (any positive float). Normalised internally.",
        examples=[{"hashtag_hockey": 10, "dobber": 8, "apples_ginos": 5}],
    )
    scoring_config_id: str = Field(..., description="UUID of a scoring_configs row")
    platform: str = Field(
        ...,
        description="Fantasy platform for position eligibility lookup",
        examples=["espn", "yahoo", "fantrax"],
    )
    league_profile_id: str | None = Field(
        None,
        description="UUID of a league_profiles row. Required to compute VORP. "
        "Omit to skip VORP (all players return vorp=null).",
    )

    @model_validator(mode="after")
    def source_weights_not_all_zero(self) -> "RankingsComputeRequest":
        if not self.source_weights or all(v == 0 for v in self.source_weights.values()):
            raise ValueError("source_weights: at least one source must have a non-zero weight")
        return self


class ProjectedStats(BaseModel):
    g: int | None = None
    a: int | None = None
    plus_minus: int | None = None
    pim: int | None = None
    ppg: int | None = None
    ppa: int | None = None
    ppp: int | None = None
    shg: int | None = None
    sha: int | None = None
    shp: int | None = None
    sog: int | None = None
    fow: int | None = None
    fol: int | None = None
    hits: int | None = None
    blocks: int | None = None
    gp: int | None = None
    # Goalie
    gs: int | None = None
    w: int | None = None
    l: int | None = None
    ga: int | None = None
    sa: int | None = None
    sv: int | None = None
    sv_pct: float | None = None
    so: int | None = None
    otl: int | None = None


class RankedPlayer(BaseModel):
    composite_rank: int
    player_id: str
    name: str
    team: str | None = None
    default_position: str | None = None
    platform_positions: list[str] = Field(default_factory=list)
    projected_fantasy_points: float | None = None
    vorp: float | None = None
    schedule_score: float | None = None
    off_night_games: int | None = None
    source_count: int = 0
    projected_stats: ProjectedStats = Field(default_factory=ProjectedStats)
    breakout_score: float | None = None
    regression_risk: float | None = None


class RankingsComputeResponse(BaseModel):
    season: str
    computed_at: datetime
    cached: bool
    rankings: list[RankedPlayer]


# ---------------------------------------------------------------------------
# Scoring configs
# ---------------------------------------------------------------------------


class ScoringConfigOut(BaseModel):
    id: str
    name: str
    stat_weights: dict[str, float]
    is_preset: bool


# ---------------------------------------------------------------------------
# League profiles
# ---------------------------------------------------------------------------


class LeagueProfileCreate(BaseModel):
    name: str
    platform: str = Field(..., pattern="^(espn|yahoo|fantrax)$")
    num_teams: int = Field(..., gt=0)
    roster_slots: dict[str, int] = Field(
        ...,
        examples=[{"C": 2, "LW": 2, "RW": 2, "D": 4, "G": 2, "UTIL": 1, "BN": 4}],
    )
    scoring_config_id: str


class LeagueProfileOut(BaseModel):
    id: str
    name: str
    platform: str
    num_teams: int
    roster_slots: dict[str, int]
    scoring_config_id: str
    created_at: datetime


# ---------------------------------------------------------------------------
# Exports
# ---------------------------------------------------------------------------


class ExportRequest(BaseModel):
    season: str
    source_weights: dict[str, float]
    scoring_config_id: str
    platform: str
    league_profile_id: str | None = None
    export_type: str = Field(..., pattern="^(pdf|excel|bundle)$")

    @model_validator(mode="after")
    def source_weights_not_all_zero(self) -> "ExportRequest":
        if not self.source_weights or all(v == 0 for v in self.source_weights.values()):
            raise ValueError("source_weights: at least one source must have a non-zero weight")
        return self
```

- [ ] **Step 2: Run existing tests to catch breakage**

```bash
cd apps/api && pytest tests/ -v --tb=short
# Expected: some ranking/export router tests now fail (that's OK — they'll be
# fixed in later tasks). Other tests (health, sources, user_kits, stripe) pass.
```

- [ ] **Step 3: Commit**

```bash
git add models/schemas.py
git commit -m "feat(schemas): replace rank-based schemas with projection-based pipeline models"
```

---

### Task 4: Projection repository

**Files:**
- Create: `apps/api/repositories/projections.py`
- Create: `apps/api/tests/repositories/test_projections.py`

The repository fetches all `player_projections` rows for a season, joined with sources, players, player_platform_positions, and schedule_scores. The returned dicts are the raw input to `services/projections.py`.

- [ ] **Step 1: Write the failing tests**

```python
# apps/api/tests/repositories/test_projections.py
from __future__ import annotations

import pytest
from unittest.mock import MagicMock, call

from repositories.projections import ProjectionRepository


@pytest.fixture
def mock_db() -> MagicMock:
    return MagicMock()


@pytest.fixture
def repo(mock_db: MagicMock) -> ProjectionRepository:
    return ProjectionRepository(mock_db)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_db_row(
    player_id: str = "p1",
    source_name: str = "dobber",
    is_paid: bool = False,
    source_user_id: str | None = None,
    g: int | None = 30,
) -> dict:
    return {
        "player_id": player_id,
        "season": "2025-26",
        "g": g,
        "a": None,
        "plus_minus": None,
        "pim": None,
        "ppg": None, "ppa": None, "ppp": None,
        "shg": None, "sha": None, "shp": None,
        "sog": None, "fow": None, "fol": None,
        "hits": None, "blocks": None, "gp": None,
        "gs": None, "w": None, "l": None, "ga": None,
        "sa": None, "sv": None, "sv_pct": None, "so": None, "otl": None,
        "sources": {
            "name": source_name,
            "default_weight": 1.0,
            "is_paid": is_paid,
            "user_id": source_user_id,
        },
        "players": {
            "name": "Connor McDavid",
            "team": "EDM",
            "position": "C",
        },
        "player_platform_positions": [{"positions": ["C"]}],
        "schedule_scores": [{"schedule_score": 0.8, "off_night_games": 24}],
    }


class TestGetBySeason:
    def test_queries_player_projections_table(
        self, repo: ProjectionRepository, mock_db: MagicMock
    ) -> None:
        mock_db.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []
        repo.get_by_season("2025-26", "espn", "user-1")
        mock_db.table.assert_called_once_with("player_projections")

    def test_filters_by_season(
        self, repo: ProjectionRepository, mock_db: MagicMock
    ) -> None:
        chain = mock_db.table.return_value.select.return_value.eq
        chain.return_value.execute.return_value.data = []
        repo.get_by_season("2025-26", "espn", "user-1")
        chain.assert_called_once_with("season", "2025-26")

    def test_returns_rows(
        self, repo: ProjectionRepository, mock_db: MagicMock
    ) -> None:
        row = _make_db_row()
        mock_db.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [row]
        result = repo.get_by_season("2025-26", "espn", "user-1")
        assert len(result) == 1

    def test_returns_empty_list_when_no_data(
        self, repo: ProjectionRepository, mock_db: MagicMock
    ) -> None:
        mock_db.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []
        assert repo.get_by_season("2025-26", "espn", "user-1") == []

    def test_excludes_other_users_custom_sources(
        self, repo: ProjectionRepository, mock_db: MagicMock
    ) -> None:
        # System source (user_id=None) and requesting user's own source are kept.
        # Another user's custom source must be excluded by the privacy filter.
        system_row = _make_db_row("p1", source_user_id=None)
        own_row = _make_db_row("p2", source_user_id="user-1")
        other_row = _make_db_row("p3", source_user_id="user-99")
        mock_db.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
            system_row, own_row, other_row
        ]
        result = repo.get_by_season("2025-26", "espn", "user-1")
        player_ids = [r["player_id"] for r in result]
        assert "p1" in player_ids   # system source — visible
        assert "p2" in player_ids   # own custom source — visible
        assert "p3" not in player_ids  # another user's source — excluded
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd apps/api && pytest tests/repositories/test_projections.py -v
# Expected: FAIL — ModuleNotFoundError
```

- [ ] **Step 3: Implement ProjectionRepository**

```python
# apps/api/repositories/projections.py
"""
Projection repository — fetches player_projections rows joined with all
context needed by the aggregation service.

Join shape (each row):
  {
    "player_id": str,
    "season": str,
    "g": int | None, "a": int | None, ... (all stat columns),
    "sources": {
        "name": str,          # machine key e.g. "dobber"
        "default_weight": float | None,
        "is_paid": bool,
        "user_id": str | None,
    },
    "players": {
        "name": str,
        "team": str | None,
        "position": str | None,   # NHL.com canonical
    },
    "player_platform_positions": [{"positions": list[str]}],  # 0 or 1 element
    "schedule_scores": [{"schedule_score": float, "off_night_games": int}],  # 0 or 1
  }
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from supabase import Client

_STAT_COLUMNS = (
    "g, a, plus_minus, pim, ppg, ppa, ppp, shg, sha, shp, "
    "sog, fow, fol, hits, blocks, gp, "
    "gs, w, l, ga, sa, sv, sv_pct, so, otl"
)


class ProjectionRepository:
    def __init__(self, db: "Client") -> None:
        self._db = db

    def get_by_season(
        self,
        season: str,
        platform: str,
        user_id: str,
    ) -> list[dict[str, Any]]:
        """Return all projection rows for a season with joined context.

        Filters sources to those visible to user_id:
          - system sources (user_id IS NULL)
          - the requesting user's own custom sources
        Platform is used to join player_platform_positions.
        """
        result = (
            self._db.table("player_projections")
            .select(
                f"player_id, season, {_STAT_COLUMNS}, "
                "sources!inner(name, default_weight, is_paid, user_id), "
                "players!inner(name, team, position), "
                f"player_platform_positions(positions).eq(platform, '{platform}'), "
                "schedule_scores(schedule_score, off_night_games)"
            )
            .eq("season", season)
            .execute()
        )
        # Privacy filter: RLS on `sources` may not be enforced via the join.
        # Post-query: keep only system sources (user_id IS NULL) or the requesting user's own.
        return [
            row for row in result.data
            if row["sources"]["user_id"] is None
            or row["sources"]["user_id"] == user_id
        ]
```

> **Note:** The PostgREST join syntax for filtered relations (platform filter on player_platform_positions) may need to be implemented as a Supabase RPC or a post-query filter depending on your Supabase client version. If the join filter is not supported, filter `player_platform_positions` in Python after fetching.

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd apps/api && pytest tests/repositories/test_projections.py -v
# Expected: all pass
```

- [ ] **Step 5: Commit**

```bash
git add repositories/projections.py tests/repositories/test_projections.py
git commit -m "feat(repo): add ProjectionRepository for player_projections"
```

---

## Chunk 3: Projection Service (core math)

### Task 5: compute_weighted_stats

**Files:**
- Create: `apps/api/services/projections.py`
- Create: `apps/api/tests/services/test_projections.py`

`compute_weighted_stats` takes a list of source rows for a single player and returns a dict of stat → weighted average (None if no source projected that stat).

- [ ] **Step 1: Write failing tests for compute_weighted_stats**

```python
# apps/api/tests/services/test_projections.py
from __future__ import annotations

import pytest

from services.projections import compute_weighted_stats, apply_scoring_config, compute_vorp


def _make_row(source_name: str, weight: float, **stats: int | None) -> dict:
    return {"source_name": source_name, "source_weight": weight, **stats}


class TestComputeWeightedStats:
    def test_single_source_returns_stat(self) -> None:
        rows = [_make_row("dobber", 10, g=30, a=45, sog=None)]
        result = compute_weighted_stats(rows)
        assert result["g"] == pytest.approx(30.0)
        assert result["a"] == pytest.approx(45.0)

    def test_null_stat_is_null_when_no_source_projects_it(self) -> None:
        rows = [_make_row("dobber", 10, g=30, a=None)]
        result = compute_weighted_stats(rows)
        assert result["a"] is None

    def test_null_excluded_per_stat(self) -> None:
        """If source A projects g=30 and source B does not (null), only A's g counts."""
        rows = [
            _make_row("dobber", 10, g=30),
            _make_row("hashtag", 10, g=None),
        ]
        result = compute_weighted_stats(rows)
        assert result["g"] == pytest.approx(30.0)

    def test_weighted_average_across_sources(self) -> None:
        rows = [
            _make_row("dobber", 10, g=30),
            _make_row("hashtag", 10, g=40),
        ]
        result = compute_weighted_stats(rows)
        assert result["g"] == pytest.approx(35.0)

    def test_unequal_weights(self) -> None:
        rows = [
            _make_row("dobber", 10, g=30),
            _make_row("hashtag", 30, g=60),
        ]
        # g = (30*10 + 60*30) / (10 + 30) = (300 + 1800) / 40 = 52.5
        result = compute_weighted_stats(rows)
        assert result["g"] == pytest.approx(52.5)

    def test_zero_stat_is_distinct_from_null(self) -> None:
        rows = [_make_row("dobber", 10, g=0)]
        result = compute_weighted_stats(rows)
        assert result["g"] == pytest.approx(0.0)
        assert result["g"] is not None

    def test_all_nulls_returns_null(self) -> None:
        rows = [
            _make_row("dobber", 10, g=None),
            _make_row("hashtag", 10, g=None),
        ]
        result = compute_weighted_stats(rows)
        assert result["g"] is None

    def test_returns_all_stat_keys(self) -> None:
        rows = [_make_row("dobber", 10, g=30)]
        result = compute_weighted_stats(rows)
        for stat in ["g", "a", "ppp", "sog", "hits", "blocks", "gp"]:
            assert stat in result

    def test_source_count_counts_sources_with_any_non_null_stat(self) -> None:
        # _source_count = # sources that projected at least one stat (any stat)
        rows = [
            _make_row("dobber", 10, g=30),   # projects g
            _make_row("hashtag", 10, g=None), # projects nothing → not counted
        ]
        result = compute_weighted_stats(rows)
        assert result["_source_count"] == 1

    def test_source_count_two_sources_projecting_different_stats(self) -> None:
        # Both sources project at least one stat — both counted even if they
        # project different stats. source_count = 2.
        rows = [
            _make_row("dobber", 10, g=30, hits=None),
            _make_row("hashtag", 10, g=None, hits=100),
        ]
        result = compute_weighted_stats(rows)
        assert result["_source_count"] == 2
        assert result["g"] == pytest.approx(30.0)   # only dobber
        assert result["hits"] == pytest.approx(100.0)  # only hashtag


class TestApplyScoringConfig:
    def test_basic_scoring(self) -> None:
        stats = {"g": 30.0, "a": 45.0, "ppp": 20.0, "sog": None}
        config = {"g": 3.0, "a": 2.0, "ppp": 1.0, "sog": 0.5}
        # g=30*3=90, a=45*2=90, ppp=20*1=20, sog=null→0
        assert apply_scoring_config(stats, config) == pytest.approx(200.0)

    def test_null_stat_contributes_zero(self) -> None:
        stats = {"g": None}
        config = {"g": 3.0}
        assert apply_scoring_config(stats, config) == pytest.approx(0.0)

    def test_unrecognised_config_key_ignored(self) -> None:
        stats = {"g": 10.0}
        config = {"g": 3.0, "fake_stat": 99.0}
        assert apply_scoring_config(stats, config) == pytest.approx(30.0)

    def test_empty_stats_returns_zero(self) -> None:
        assert apply_scoring_config({}, {"g": 3.0}) == pytest.approx(0.0)

    def test_zero_weight_stat_not_counted(self) -> None:
        stats = {"g": 30.0, "hits": 100.0}
        config = {"g": 3.0, "hits": 0.0}
        assert apply_scoring_config(stats, config) == pytest.approx(90.0)


class TestComputeVorp:
    def _make_players(self, fps: list[float | None]) -> list[dict]:
        return [
            {
                "player_id": f"p{i}",
                "default_position": "C",
                "projected_fantasy_points": fp,
            }
            for i, fp in enumerate(fps)
        ]

    def _make_profile(
        self, num_teams: int = 10, c_slots: int = 2
    ) -> dict:
        return {
            "num_teams": num_teams,
            "roster_slots": {"C": c_slots, "LW": 2, "RW": 2, "D": 4, "G": 2},
        }

    def test_replacement_level_is_nth_player(self) -> None:
        # 10 teams * 2 C slots = 20 starters; replacement = rank 21
        fps = list(range(100, 79, -1))  # 21 players: 100, 99, ..., 80
        players = self._make_players(fps)
        result = compute_vorp(players, self._make_profile(10, 2))
        # replacement level = player at index 20 (0-based) = 80 FP
        # player 0 (100 FP) → vorp = 100 - 80 = 20
        assert result["p0"] == pytest.approx(20.0)

    def test_replacement_level_player_has_zero_vorp(self) -> None:
        fps = list(range(100, 79, -1))  # 21 players: 100, 99, ..., 80
        players = self._make_players(fps)
        result = compute_vorp(players, self._make_profile(10, 2))
        # replacement level = player at index 20 (rank 21) = 80 FP → vorp = 0
        assert result["p20"] == pytest.approx(0.0)

    def test_player_below_replacement_has_negative_vorp(self) -> None:
        # 22 players; replacement threshold = 10 teams × 2 slots + 1 = 21
        fps = list(range(100, 78, -1))  # 22 players: 100, 99, ..., 79
        players = self._make_players(fps)
        result = compute_vorp(players, self._make_profile(10, 2))
        # replacement level = player at rank 21 (index 20) = 80 FP
        # player at index 21 has 79 FP → vorp = 79 − 80 = −1
        assert result["p21"] == pytest.approx(-1.0)

    def test_null_fp_returns_null_vorp(self) -> None:
        fps = [100.0, None]
        players = self._make_players(fps)
        result = compute_vorp(players, self._make_profile(1, 1))
        assert result["p1"] is None

    def test_fewer_players_than_replacement_uses_last(self) -> None:
        # Only 3 C players but replacement threshold is 21 → use last (lowest FP)
        players = self._make_players([100.0, 90.0, 80.0])
        result = compute_vorp(players, self._make_profile(10, 2))
        # replacement = 80 (last available)
        assert result["p0"] == pytest.approx(20.0)
        assert result["p2"] == pytest.approx(0.0)

    def test_vorp_null_when_no_players_in_position(self) -> None:
        players = [{"player_id": "p1", "default_position": "G", "projected_fantasy_points": 50.0}]
        profile = {"num_teams": 10, "roster_slots": {"C": 2}}  # no G slot
        result = compute_vorp(players, profile)
        assert result["p1"] is None
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd apps/api && pytest tests/services/test_projections.py -v
# Expected: FAIL — ModuleNotFoundError: No module named 'services.projections'
```

- [ ] **Step 3: Implement compute_weighted_stats and apply_scoring_config**

```python
# apps/api/services/projections.py
"""
Projection aggregation service — pure functions, no DB access.

Pipeline:
  1. compute_weighted_stats()   — weighted average per stat across sources
  2. apply_scoring_config()     — stats × scoring weights → fantasy points
  3. compute_vorp()             — fantasy points → VORP per position
  4. aggregate_projections()    — top-level orchestrator
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any

# All stat columns in player_projections (skater + goalie)
SKATER_STATS: list[str] = [
    "g", "a", "plus_minus", "pim", "ppg", "ppa", "ppp",
    "shg", "sha", "shp", "sog", "fow", "fol", "hits", "blocks", "gp",
]
GOALIE_STATS: list[str] = ["gs", "w", "l", "ga", "sa", "sv", "sv_pct", "so", "otl"]
ALL_STATS: list[str] = SKATER_STATS + GOALIE_STATS


def compute_weighted_stats(
    rows: list[dict[str, Any]],
) -> dict[str, float | None]:
    """Compute weighted average per stat for a single player across sources.

    Args:
        rows: List of source rows for one player. Each dict must have
              ``source_weight`` (float) and one key per stat column.
              null stat value = source did not project that stat.

    Returns:
        Dict mapping stat_name → weighted average (None if no source projected it).
        Also includes ``_source_count``: count of sources that projected any stat.
    """
    weighted_sum: dict[str, float] = defaultdict(float)
    total_weight: dict[str, float] = defaultdict(float)

    sources_with_any_stat: set[str] = set()

    for row in rows:
        w = row.get("source_weight", 0.0)
        if w <= 0:
            continue
        source = row.get("source_name", "")
        for stat in ALL_STATS:
            val = row.get(stat)
            if val is not None:
                weighted_sum[stat] += val * w
                total_weight[stat] += w
                sources_with_any_stat.add(source)

    result: dict[str, float | None] = {}
    for stat in ALL_STATS:
        if total_weight[stat] > 0:
            result[stat] = weighted_sum[stat] / total_weight[stat]
        else:
            result[stat] = None

    result["_source_count"] = len(sources_with_any_stat)
    return result


def apply_scoring_config(
    stats: dict[str, float | None],
    scoring_config: dict[str, float],
) -> float:
    """Convert projected stats to fantasy points using a scoring config.

    Args:
        stats:          stat_name → weighted average (None treated as 0).
        scoring_config: stat_name → fantasy point weight.
                        Keys not in stats are ignored.

    Returns:
        Projected fantasy points (float). Returns 0.0 for all-null stats.
    """
    total = 0.0
    for stat, weight in scoring_config.items():
        val = stats.get(stat)
        if val is not None and weight:
            total += val * weight
    return total
```

- [ ] **Step 4: Run compute_weighted_stats and apply_scoring_config tests**

```bash
cd apps/api && pytest tests/services/test_projections.py::TestComputeWeightedStats tests/services/test_projections.py::TestApplyScoringConfig -v
# Expected: all pass
```

---

### Task 6: compute_vorp

Add `compute_vorp` to `services/projections.py`.

- [ ] **Step 1: Run compute_vorp tests to confirm they fail (red phase)**

The `TestComputeVorp` tests were written in Task 5 Step 1. Run only those tests now to confirm they fail before implementing.

```bash
cd apps/api && pytest tests/services/test_projections.py::TestComputeVorp -v
# Expected: FAIL — NameError: name 'compute_vorp' is not defined
```

- [ ] **Step 2: Implement compute_vorp**

Append to `apps/api/services/projections.py`:

```python
def compute_vorp(
    players: list[dict[str, Any]],
    league_profile: dict[str, Any],
) -> dict[str, float | None]:
    """Compute Value Over Replacement Player for each player.

    Args:
        players: List of player dicts, each with:
                   - player_id: str
                   - default_position: str  (NHL.com canonical: C, LW, RW, D, G)
                   - projected_fantasy_points: float | None
        league_profile: Dict with num_teams (int) and roster_slots (dict[str, int]).
                        roster_slots keys should be position codes matching
                        players.default_position.

    Returns:
        Dict of player_id → VORP (float | None).
        None when: player has null FP, or position group has no roster slot.
    """
    num_teams: int = league_profile["num_teams"]
    roster_slots: dict[str, int] = league_profile.get("roster_slots", {})

    # Group by NHL.com position
    by_position: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for p in players:
        by_position[p["default_position"]].append(p)

    # Sort each position group descending by FP (nulls last)
    for pos_players in by_position.values():
        pos_players.sort(
            key=lambda p: (
                p["projected_fantasy_points"] is None,
                -(p["projected_fantasy_points"] or 0),
            )
        )

    result: dict[str, float | None] = {}

    for player in players:
        pid = player["player_id"]
        pos = player["default_position"]
        fp = player["projected_fantasy_points"]

        if fp is None:
            result[pid] = None
            continue

        slots = roster_slots.get(pos, 0)
        if slots == 0:
            result[pid] = None
            continue

        # replacement level = player at index (num_teams × slots), 0-based
        threshold_idx = num_teams * slots
        pos_group = by_position[pos]
        eligible = [p for p in pos_group if p["projected_fantasy_points"] is not None]

        if not eligible:
            result[pid] = None
            continue

        # If fewer players than threshold, use last available
        replacement_idx = min(threshold_idx, len(eligible) - 1)
        replacement_fp = eligible[replacement_idx]["projected_fantasy_points"]

        result[pid] = fp - replacement_fp  # may be negative

    return result
```

- [ ] **Step 2: Run compute_vorp tests**

```bash
cd apps/api && pytest tests/services/test_projections.py::TestComputeVorp -v
# Expected: all pass
```

- [ ] **Step 3: Run all projection service tests**

```bash
cd apps/api && pytest tests/services/test_projections.py -v
# Expected: all pass
```

- [ ] **Step 4: Commit**

```bash
git add services/projections.py tests/services/test_projections.py
git commit -m "feat(services): add projection aggregation service (weighted stats, scoring, VORP)"
```

---

### Task 7: aggregate_projections orchestrator

Add `aggregate_projections` to `services/projections.py` — this is the top-level function the router calls.

- [ ] **Step 1: Write failing integration test**

Append to `apps/api/tests/services/test_projections.py`:

```python
from services.projections import aggregate_projections


class TestAggregateProjections:
    """Integration test — exercises the full pipeline with minimal mocked data."""

    def _make_db_rows(self) -> list[dict]:
        base = {
            "season": "2025-26",
            "a": None, "plus_minus": None, "pim": None,
            "ppg": None, "ppa": None, "ppp": None,
            "shg": None, "sha": None, "shp": None,
            "sog": None, "fow": None, "fol": None,
            "hits": None, "blocks": None, "gp": 82,
            "gs": None, "w": None, "l": None, "ga": None,
            "sa": None, "sv": None, "sv_pct": None, "so": None, "otl": None,
        }
        return [
            {
                **base,
                "player_id": "p1",
                "g": 50,
                "sources": {"name": "dobber", "is_paid": False, "user_id": None},
                "players": {"name": "McDavid", "team": "EDM", "position": "C"},
                "player_platform_positions": [{"positions": ["C"]}],
                "schedule_scores": [{"schedule_score": 0.8, "off_night_games": 24}],
            },
            {
                **base,
                "player_id": "p2",
                "g": 30,
                "sources": {"name": "dobber", "is_paid": False, "user_id": None},
                "players": {"name": "Smith", "team": "DAL", "position": "LW"},
                "player_platform_positions": [{"positions": ["LW"]}],
                "schedule_scores": [],
            },
        ]

    def test_returns_ranked_players(self) -> None:
        rows = self._make_db_rows()
        source_weights = {"dobber": 10}
        scoring_config = {"g": 3.0}
        result = aggregate_projections(rows, source_weights, scoring_config)
        assert len(result) == 2

    def test_sorted_by_fantasy_points_descending(self) -> None:
        rows = self._make_db_rows()
        result = aggregate_projections(rows, {"dobber": 10}, {"g": 3.0})
        fps = [r["projected_fantasy_points"] for r in result]
        assert fps == sorted(fps, reverse=True)

    def test_composite_rank_assigned(self) -> None:
        rows = self._make_db_rows()
        result = aggregate_projections(rows, {"dobber": 10}, {"g": 3.0})
        assert result[0]["composite_rank"] == 1
        assert result[1]["composite_rank"] == 2

    def test_schedule_score_attached(self) -> None:
        rows = self._make_db_rows()
        result = aggregate_projections(rows, {"dobber": 10}, {"g": 3.0})
        p1 = next(r for r in result if r["player_id"] == "p1")
        assert p1["schedule_score"] == pytest.approx(0.8)
        assert p1["off_night_games"] == 24

    def test_missing_schedule_score_is_null(self) -> None:
        rows = self._make_db_rows()
        result = aggregate_projections(rows, {"dobber": 10}, {"g": 3.0})
        p2 = next(r for r in result if r["player_id"] == "p2")
        assert p2["schedule_score"] is None
        assert p2["off_night_games"] is None

    def test_vorp_computed_when_profile_provided(self) -> None:
        rows = self._make_db_rows()
        profile = {"num_teams": 1, "roster_slots": {"C": 1, "LW": 1}}
        result = aggregate_projections(rows, {"dobber": 10}, {"g": 3.0}, profile)
        for r in result:
            assert "vorp" in r

    def test_vorp_null_when_no_profile(self) -> None:
        rows = self._make_db_rows()
        result = aggregate_projections(rows, {"dobber": 10}, {"g": 3.0})
        for r in result:
            assert r["vorp"] is None

    def test_unknown_source_weight_ignored(self) -> None:
        rows = self._make_db_rows()
        # "ghost_source" not in DB rows — should not break
        result = aggregate_projections(rows, {"ghost_source": 10}, {"g": 3.0})
        # All players have null FP (no matching source) → sort last
        for r in result:
            assert r["projected_fantasy_points"] is None

    def test_zero_weight_source_produces_null_fp(self) -> None:
        # Source is present in source_weights but weight = 0.
        # Weighted average denominator = 0 → null FP (not zero FP).
        rows = self._make_db_rows()
        source_name = rows[0]["sources"]["name"]  # e.g. "hashtag"
        result = aggregate_projections(rows, {source_name: 0}, {"g": 3.0})
        for r in result:
            assert r["projected_fantasy_points"] is None
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd apps/api && pytest tests/services/test_projections.py::TestAggregateProjections -v
# Expected: FAIL — aggregate_projections not yet defined
```

- [ ] **Step 3: Implement aggregate_projections**

Append to `apps/api/services/projections.py`:

```python
def aggregate_projections(
    rows: list[dict[str, Any]],
    source_weights: dict[str, float],
    scoring_config: dict[str, float],
    league_profile: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Orchestrate the full projection aggregation pipeline.

    Args:
        rows:           Raw DB rows from ProjectionRepository.get_by_season().
                        Each row is one (player, source) pair with all stat cols.
        source_weights: User's source weights — {source_name: weight}.
                        Sources absent from this dict are excluded.
        scoring_config: Scoring weights — {stat_name: fantasy_pt_weight}.
        league_profile: Optional. If provided, VORP is computed per position.

    Returns:
        List of player dicts sorted by projected_fantasy_points descending
        (nulls last). Each dict matches the RankedPlayer schema.
    """
    # 1. Group rows by player_id, injecting source_weight from user's config
    player_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
    player_meta: dict[str, dict[str, Any]] = {}

    for row in rows:
        source_name = row.get("sources", {}).get("name", "")
        source_uid = row.get("sources", {}).get("user_id")
        weight = source_weights.get(source_name, 0.0)
        if weight <= 0:
            continue

        pid = row["player_id"]
        player_rows[pid].append({**row, "source_name": source_name, "source_weight": weight})

        if pid not in player_meta:
            players_join = row.get("players", {})
            platform_pos = row.get("player_platform_positions") or []
            schedule = row.get("schedule_scores") or []
            player_meta[pid] = {
                "player_id": pid,
                "name": players_join.get("name"),
                "team": players_join.get("team"),
                "default_position": players_join.get("position"),
                "platform_positions": platform_pos[0].get("positions", []) if platform_pos else [],
                "schedule_score": schedule[0].get("schedule_score") if schedule else None,
                "off_night_games": schedule[0].get("off_night_games") if schedule else None,
            }

    # 2. For players with no matching source, still include them (null FP, sorted last)
    #    First collect all player_ids from rows (with or without weight match)
    all_pids: set[str] = set()
    for row in rows:
        pid = row["player_id"]
        all_pids.add(pid)
        if pid not in player_meta:
            players_join = row.get("players", {})
            platform_pos = row.get("player_platform_positions") or []
            schedule = row.get("schedule_scores") or []
            player_meta[pid] = {
                "player_id": pid,
                "name": players_join.get("name"),
                "team": players_join.get("team"),
                "default_position": players_join.get("position"),
                "platform_positions": platform_pos[0].get("positions", []) if platform_pos else [],
                "schedule_score": schedule[0].get("schedule_score") if schedule else None,
                "off_night_games": schedule[0].get("off_night_games") if schedule else None,
            }

    # 3. Compute weighted stats and fantasy points per player
    aggregated: list[dict[str, Any]] = []
    for pid in all_pids:
        meta = player_meta[pid]
        p_rows = player_rows.get(pid, [])

        if p_rows:
            stats = compute_weighted_stats(p_rows)
            source_count = int(stats.pop("_source_count", 0))
            fp = apply_scoring_config(stats, scoring_config)
        else:
            stats = {s: None for s in ALL_STATS}
            source_count = 0
            fp = None

        aggregated.append({
            **meta,
            "projected_fantasy_points": fp,
            "vorp": None,  # filled in step 4
            "source_count": source_count,
            "projected_stats": {s: stats.get(s) for s in ALL_STATS},
            "breakout_score": None,
            "regression_risk": None,
        })

    # 4. Compute VORP if league profile provided
    if league_profile:
        vorps = compute_vorp(aggregated, league_profile)
        for player in aggregated:
            player["vorp"] = vorps.get(player["player_id"])

    # 5. Sort by fantasy points descending (nulls last)
    aggregated.sort(
        key=lambda p: (
            p["projected_fantasy_points"] is None,
            -(p["projected_fantasy_points"] or 0),
        )
    )

    # 6. Assign composite_rank
    for i, player in enumerate(aggregated, 1):
        player["composite_rank"] = i

    return aggregated
```

- [ ] **Step 4: Run all projection service tests**

```bash
cd apps/api && pytest tests/services/test_projections.py -v
# Expected: all pass
```

- [ ] **Step 5: Commit**

```bash
git add services/projections.py tests/services/test_projections.py
git commit -m "feat(services): add aggregate_projections orchestrator"
```

---

## Chunk 4: Cache Update + League Profiles + Rankings Router

### Task 8: Update CacheService key format

**Files:**
- Modify: `apps/api/services/cache.py`
- Modify: `apps/api/tests/services/test_cache.py`

The cache key must use SHA-256 (not MD5) and include all four parameters: `source_weights`, `scoring_config_id`, `platform`, `league_profile_id`.

- [ ] **Step 1: Write failing tests for new key format**

Add to `apps/api/tests/services/test_cache.py`:

```python
# At the top of the existing test file, add these test cases to the existing
# test class (or create a new class TestRankingsKeyFormat):

from services.cache import _make_rankings_key


class TestMakeRankingsKey:
    def test_key_includes_season_prefix(self) -> None:
        key = _make_rankings_key(
            "2025-26",
            source_weights={"dobber": 10},
            scoring_config_id="abc",
            platform="espn",
            league_profile_id=None,
        )
        assert key.startswith("rankings:2025-26:")

    def test_key_is_deterministic(self) -> None:
        params = dict(
            source_weights={"dobber": 10, "hashtag": 5},
            scoring_config_id="abc",
            platform="espn",
            league_profile_id=None,
        )
        k1 = _make_rankings_key("2025-26", **params)
        k2 = _make_rankings_key("2025-26", **params)
        assert k1 == k2

    def test_key_independent_of_weight_insertion_order(self) -> None:
        k1 = _make_rankings_key(
            "2025-26",
            source_weights={"a": 1, "b": 2},
            scoring_config_id="x",
            platform="espn",
            league_profile_id=None,
        )
        k2 = _make_rankings_key(
            "2025-26",
            source_weights={"b": 2, "a": 1},
            scoring_config_id="x",
            platform="espn",
            league_profile_id=None,
        )
        assert k1 == k2

    def test_different_scoring_config_produces_different_key(self) -> None:
        k1 = _make_rankings_key("2025-26", source_weights={}, scoring_config_id="a", platform="espn", league_profile_id=None)
        k2 = _make_rankings_key("2025-26", source_weights={}, scoring_config_id="b", platform="espn", league_profile_id=None)
        assert k1 != k2

    def test_different_platform_produces_different_key(self) -> None:
        k1 = _make_rankings_key("2025-26", source_weights={}, scoring_config_id="a", platform="espn", league_profile_id=None)
        k2 = _make_rankings_key("2025-26", source_weights={}, scoring_config_id="a", platform="yahoo", league_profile_id=None)
        assert k1 != k2

    def test_different_league_profile_produces_different_key(self) -> None:
        k1 = _make_rankings_key("2025-26", source_weights={}, scoring_config_id="a", platform="espn", league_profile_id="lp1")
        k2 = _make_rankings_key("2025-26", source_weights={}, scoring_config_id="a", platform="espn", league_profile_id="lp2")
        assert k1 != k2

    def test_uses_sha256_not_md5(self) -> None:
        key = _make_rankings_key("2025-26", source_weights={}, scoring_config_id="a", platform="espn", league_profile_id=None)
        digest = key.split(":")[-1]
        assert len(digest) == 64  # SHA-256 hex = 64 chars
```

- [ ] **Step 2: Run to verify they fail**

```bash
cd apps/api && pytest tests/services/test_cache.py::TestMakeRankingsKey -v
# Expected: FAIL — old signature doesn't match
```

- [ ] **Step 3: Update _make_rankings_key and CacheService methods**

In `apps/api/services/cache.py`, replace `_make_rankings_key` and update the public methods:

```python
def _make_rankings_key(
    season: str,
    source_weights: dict[str, float],
    scoring_config_id: str,
    platform: str,
    league_profile_id: str | None,
) -> str:
    """Deterministic SHA-256 cache key for a rankings compute request."""
    canonical = json.dumps(
        {
            "source_weights": dict(sorted(source_weights.items())),
            "scoring_config_id": scoring_config_id,
            "platform": platform,
            "league_profile_id": league_profile_id,
        },
        sort_keys=True,
    )
    digest = hashlib.sha256(canonical.encode()).hexdigest()
    return f"rankings:{season}:{digest}"
```

Then update `get_rankings` and `set_rankings` to accept the new parameters:

```python
def get_rankings(
    self,
    season: str,
    source_weights: dict[str, float],
    scoring_config_id: str,
    platform: str,
    league_profile_id: str | None,
) -> list[dict[str, Any]] | None:
    if not self._client:
        return None
    try:
        key = _make_rankings_key(season, source_weights, scoring_config_id, platform, league_profile_id)
        raw = self._client.get(key)
        if raw:
            return json.loads(raw)
    except Exception as exc:
        logger.warning("Cache GET failed: %s", exc)
    return None

def set_rankings(
    self,
    season: str,
    source_weights: dict[str, float],
    scoring_config_id: str,
    platform: str,
    league_profile_id: str | None,
    data: list[dict[str, Any]],
) -> None:
    if not self._client:
        return
    try:
        key = _make_rankings_key(season, source_weights, scoring_config_id, platform, league_profile_id)
        self._client.setex(key, RANKINGS_TTL_SECONDS, json.dumps(data))
    except Exception as exc:
        logger.warning("Cache SET failed: %s", exc)
```

- [ ] **Step 4: Run cache tests**

```bash
cd apps/api && pytest tests/services/test_cache.py -v
# Expected: all pass
```

- [ ] **Step 5: Commit**

```bash
git add services/cache.py tests/services/test_cache.py
git commit -m "feat(cache): update rankings key to SHA-256 with scoring_config + platform params"
```

---

### Task 9: League profiles repository + router

**Files:**
- Create: `apps/api/repositories/league_profiles.py`
- Create: `apps/api/routers/league_profiles.py`
- Create: `apps/api/tests/repositories/test_league_profiles.py`
- Create: `apps/api/tests/routers/test_league_profiles.py`
- Modify: `apps/api/core/dependencies.py` (add `get_league_profile_repository`)
- Modify: `apps/api/main.py` (register router)

- [ ] **Step 1: Write failing repository tests**

```python
# apps/api/tests/repositories/test_league_profiles.py
from __future__ import annotations

import pytest
from unittest.mock import MagicMock

from repositories.league_profiles import LeagueProfileRepository

PROFILE_ROW = {
    "id": "lp-1",
    "user_id": "u-1",
    "name": "My ESPN League",
    "platform": "espn",
    "num_teams": 12,
    "roster_slots": {"C": 2, "LW": 2, "RW": 2, "D": 4, "G": 2},
    "scoring_config_id": "sc-1",
    "created_at": "2026-03-01T00:00:00+00:00",
}


@pytest.fixture
def mock_db() -> MagicMock:
    return MagicMock()


@pytest.fixture
def repo(mock_db: MagicMock) -> LeagueProfileRepository:
    return LeagueProfileRepository(mock_db)


class TestList:
    def test_queries_league_profiles(self, repo: LeagueProfileRepository, mock_db: MagicMock) -> None:
        mock_db.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []
        repo.list(user_id="u-1")
        mock_db.table.assert_called_once_with("league_profiles")

    def test_filters_by_user_id(self, repo: LeagueProfileRepository, mock_db: MagicMock) -> None:
        chain = mock_db.table.return_value.select.return_value.eq
        chain.return_value.execute.return_value.data = []
        repo.list(user_id="u-1")
        chain.assert_called_once_with("user_id", "u-1")

    def test_returns_profiles(self, repo: LeagueProfileRepository, mock_db: MagicMock) -> None:
        mock_db.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [PROFILE_ROW]
        assert repo.list("u-1") == [PROFILE_ROW]


class TestCreate:
    def test_inserts_profile(self, repo: LeagueProfileRepository, mock_db: MagicMock) -> None:
        mock_db.table.return_value.insert.return_value.execute.return_value.data = [PROFILE_ROW]
        result = repo.create({
            "user_id": "u-1",
            "name": "My ESPN League",
            "platform": "espn",
            "num_teams": 12,
            "roster_slots": {},
            "scoring_config_id": "sc-1",
        })
        mock_db.table.assert_called_once_with("league_profiles")
        assert result == PROFILE_ROW

    def test_inserts_correct_user_id(self, repo: LeagueProfileRepository, mock_db: MagicMock) -> None:
        mock_db.table.return_value.insert.return_value.execute.return_value.data = [PROFILE_ROW]
        repo.create({"user_id": "u-1", "name": "x", "platform": "espn", "num_teams": 10, "roster_slots": {}, "scoring_config_id": "sc-1"})
        insert_arg = mock_db.table.return_value.insert.call_args.args[0]
        assert insert_arg["user_id"] == "u-1"


class TestGet:
    def test_returns_profile_when_found(self, repo: LeagueProfileRepository, mock_db: MagicMock) -> None:
        mock_db.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value.data = [PROFILE_ROW]
        result = repo.get(profile_id="lp-1", user_id="u-1")
        assert result == PROFILE_ROW

    def test_returns_none_when_not_found(self, repo: LeagueProfileRepository, mock_db: MagicMock) -> None:
        mock_db.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value.data = []
        assert repo.get("lp-1", "u-1") is None
```

- [ ] **Step 2: Run to verify they fail**

```bash
cd apps/api && pytest tests/repositories/test_league_profiles.py -v
# Expected: FAIL
```

- [ ] **Step 3: Implement LeagueProfileRepository**

```python
# apps/api/repositories/league_profiles.py
from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from supabase import Client


class LeagueProfileRepository:
    def __init__(self, db: "Client") -> None:
        self._db = db

    def list(self, user_id: str) -> list[dict[str, Any]]:
        result = (
            self._db.table("league_profiles")
            .select("*")
            .eq("user_id", user_id)
            .execute()
        )
        return result.data

    def create(self, data: dict[str, Any]) -> dict[str, Any]:
        result = self._db.table("league_profiles").insert(data).execute()
        return result.data[0]

    def get(self, profile_id: str, user_id: str) -> dict[str, Any] | None:
        result = (
            self._db.table("league_profiles")
            .select("*")
            .eq("id", profile_id)
            .eq("user_id", user_id)
            .execute()
        )
        return result.data[0] if result.data else None
```

- [ ] **Step 4: Run repository tests**

```bash
cd apps/api && pytest tests/repositories/test_league_profiles.py -v
# Expected: all pass
```

- [ ] **Step 5: Write failing router tests**

```python
# apps/api/tests/routers/test_league_profiles.py
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock

from main import app
from core.dependencies import get_current_user, get_league_profile_repository

MOCK_USER = {"id": "u-1", "email": "test@example.com"}
PROFILE_ROW = {
    "id": "lp-1",
    "user_id": "u-1",
    "name": "My ESPN League",
    "platform": "espn",
    "num_teams": 12,
    "roster_slots": {"C": 2},
    "scoring_config_id": "sc-1",
    "created_at": "2026-03-01T00:00:00+00:00",
}
CREATE_BODY = {
    "name": "My ESPN League",
    "platform": "espn",
    "num_teams": 12,
    "roster_slots": {"C": 2},
    "scoring_config_id": "sc-1",
}


@pytest.fixture
def mock_db() -> MagicMock:
    return MagicMock()


@pytest.fixture
def client(mock_db: MagicMock) -> TestClient:
    app.dependency_overrides[get_current_user] = lambda: MOCK_USER
    app.dependency_overrides[get_league_profile_repository] = lambda: mock_db
    yield TestClient(app)
    app.dependency_overrides.clear()


class TestListLeagueProfiles:
    def test_returns_200(self, client: TestClient, mock_db: MagicMock) -> None:
        mock_db.list.return_value = [PROFILE_ROW]
        assert client.get("/league-profiles").status_code == 200

    def test_returns_list(self, client: TestClient, mock_db: MagicMock) -> None:
        mock_db.list.return_value = [PROFILE_ROW]
        data = client.get("/league-profiles").json()
        assert isinstance(data, list)
        assert len(data) == 1

    def test_filters_by_user(self, client: TestClient, mock_db: MagicMock) -> None:
        mock_db.list.return_value = []
        client.get("/league-profiles")
        mock_db.list.assert_called_once_with(user_id=MOCK_USER["id"])


class TestCreateLeagueProfile:
    def test_returns_201(self, client: TestClient, mock_db: MagicMock) -> None:
        mock_db.create.return_value = PROFILE_ROW
        assert client.post("/league-profiles", json=CREATE_BODY).status_code == 201

    def test_creates_with_user_id(self, client: TestClient, mock_db: MagicMock) -> None:
        mock_db.create.return_value = PROFILE_ROW
        client.post("/league-profiles", json=CREATE_BODY)
        call_data = mock_db.create.call_args.args[0]
        assert call_data["user_id"] == MOCK_USER["id"]

    def test_missing_name_returns_422(self, client: TestClient) -> None:
        body = {k: v for k, v in CREATE_BODY.items() if k != "name"}
        assert client.post("/league-profiles", json=body).status_code == 422

    def test_invalid_platform_returns_422(self, client: TestClient) -> None:
        assert client.post(
            "/league-profiles", json={**CREATE_BODY, "platform": "sleeper"}
        ).status_code == 422
```

- [ ] **Step 6: Run to verify they fail**

```bash
cd apps/api && pytest tests/routers/test_league_profiles.py -v
# Expected: FAIL
```

- [ ] **Step 7: Implement league_profiles router**

```python
# apps/api/routers/league_profiles.py
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from core.dependencies import get_current_user, get_league_profile_repository
from models.schemas import LeagueProfileCreate, LeagueProfileOut
from repositories.league_profiles import LeagueProfileRepository

router = APIRouter(prefix="/league-profiles", tags=["league-profiles"])


@router.get("", response_model=list[LeagueProfileOut])
async def list_league_profiles(
    user: dict[str, Any] = Depends(get_current_user),
    repo: LeagueProfileRepository = Depends(get_league_profile_repository),
) -> list[LeagueProfileOut]:
    return repo.list(user_id=user["id"])


@router.post("", response_model=LeagueProfileOut, status_code=201)
async def create_league_profile(
    body: LeagueProfileCreate,
    user: dict[str, Any] = Depends(get_current_user),
    repo: LeagueProfileRepository = Depends(get_league_profile_repository),
) -> LeagueProfileOut:
    try:
        row = repo.create({**body.model_dump(), "user_id": user["id"]})
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to create league profile")
    return LeagueProfileOut(**row)
```

- [ ] **Step 8: Add dependency + register router**

In `apps/api/core/dependencies.py`, add:

```python
from repositories.league_profiles import LeagueProfileRepository

def get_league_profile_repository() -> LeagueProfileRepository:
    return LeagueProfileRepository(get_db())
```

In `apps/api/main.py`, add:

```python
from routers import exports, health, league_profiles, rankings, sources, stripe, user_kits
# ...
app.include_router(league_profiles.router)
```

- [ ] **Step 9: Run all tests**

```bash
cd apps/api && pytest tests/ -v --tb=short
# Expected: league_profile tests pass; ranking router tests still fail (fixed next)
```

- [ ] **Step 10: Commit**

```bash
git add repositories/league_profiles.py routers/league_profiles.py \
        tests/repositories/test_league_profiles.py tests/routers/test_league_profiles.py \
        core/dependencies.py main.py
git commit -m "feat(league-profiles): add repository, router, and dependency wiring"
```

---

### Task 10: Rewrite rankings router

**Files:**
- Modify: `apps/api/routers/rankings.py`
- Modify: `apps/api/core/dependencies.py` (add `get_projection_repository`)
- Modify: `apps/api/tests/routers/test_rankings.py`

The router now calls `aggregate_projections()` instead of the old rank-based pipeline. It also fetches the `scoring_config` and optionally the `league_profile` from the DB.

- [ ] **Step 1: Write failing router tests**

Replace `apps/api/tests/routers/test_rankings.py` entirely:

```python
# apps/api/tests/routers/test_rankings.py
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch

from main import app
from core.dependencies import (
    get_cache_service,
    get_current_user,
    get_league_profile_repository,
    get_projection_repository,
)

MOCK_USER = {"id": "u-1", "email": "test@example.com"}

COMPUTE_BODY = {
    "season": "2025-26",
    "source_weights": {"dobber": 10},
    "scoring_config_id": "sc-1",
    "platform": "espn",
    "league_profile_id": None,
}

SCORING_CONFIG = {"g": 3.0, "a": 2.0}

DB_ROW = {
    "player_id": "p1",
    "season": "2025-26",
    "g": 50, "a": 45,
    "plus_minus": None, "pim": None, "ppg": None, "ppa": None, "ppp": None,
    "shg": None, "sha": None, "shp": None, "sog": None, "fow": None,
    "fol": None, "hits": None, "blocks": None, "gp": 82,
    "gs": None, "w": None, "l": None, "ga": None, "sa": None,
    "sv": None, "sv_pct": None, "so": None, "otl": None,
    "sources": {"name": "dobber", "is_paid": False, "user_id": None},
    "players": {"name": "McDavid", "team": "EDM", "position": "C"},
    "player_platform_positions": [{"positions": ["C"]}],
    "schedule_scores": [{"schedule_score": 0.8, "off_night_games": 24}],
}


@pytest.fixture
def mock_proj_repo() -> MagicMock:
    repo = MagicMock()
    repo.get_by_season.return_value = [DB_ROW]
    return repo


@pytest.fixture
def mock_cache() -> MagicMock:
    cache = MagicMock()
    cache.get_rankings.return_value = None  # cache miss by default
    return cache


@pytest.fixture
def mock_lp_repo() -> MagicMock:
    repo = MagicMock()
    repo.get.return_value = None
    return repo


@pytest.fixture
def client(mock_proj_repo: MagicMock, mock_cache: MagicMock, mock_lp_repo: MagicMock) -> TestClient:
    app.dependency_overrides[get_current_user] = lambda: MOCK_USER
    app.dependency_overrides[get_projection_repository] = lambda: mock_proj_repo
    app.dependency_overrides[get_cache_service] = lambda: mock_cache
    app.dependency_overrides[get_league_profile_repository] = lambda: mock_lp_repo
    with patch("routers.rankings._get_scoring_config", return_value=SCORING_CONFIG):
        yield TestClient(app)
    app.dependency_overrides.clear()


class TestComputeRankings:
    def test_returns_200(self, client: TestClient) -> None:
        assert client.post("/rankings/compute", json=COMPUTE_BODY).status_code == 200

    def test_response_has_rankings(self, client: TestClient) -> None:
        data = client.post("/rankings/compute", json=COMPUTE_BODY).json()
        assert "rankings" in data
        assert isinstance(data["rankings"], list)

    def test_response_has_season(self, client: TestClient) -> None:
        data = client.post("/rankings/compute", json=COMPUTE_BODY).json()
        assert data["season"] == "2025-26"

    def test_ranked_player_has_projected_fantasy_points(self, client: TestClient) -> None:
        data = client.post("/rankings/compute", json=COMPUTE_BODY).json()
        player = data["rankings"][0]
        assert "projected_fantasy_points" in player

    def test_ranked_player_has_projected_stats(self, client: TestClient) -> None:
        data = client.post("/rankings/compute", json=COMPUTE_BODY).json()
        player = data["rankings"][0]
        assert "projected_stats" in player
        assert "g" in player["projected_stats"]

    def test_ranked_player_has_vorp_null_when_no_profile(self, client: TestClient) -> None:
        data = client.post("/rankings/compute", json=COMPUTE_BODY).json()
        assert data["rankings"][0]["vorp"] is None

    def test_cache_hit_returns_cached(
        self, mock_proj_repo: MagicMock, mock_cache: MagicMock, mock_lp_repo: MagicMock
    ) -> None:
        cached_player = {**DB_ROW, "composite_rank": 1, "projected_fantasy_points": 200.0,
                         "vorp": None, "schedule_score": None, "off_night_games": None,
                         "source_count": 1, "projected_stats": {}, "platform_positions": [],
                         "default_position": "C"}
        mock_cache.get_rankings.return_value = [cached_player]
        app.dependency_overrides[get_current_user] = lambda: MOCK_USER
        app.dependency_overrides[get_projection_repository] = lambda: mock_proj_repo
        app.dependency_overrides[get_cache_service] = lambda: mock_cache
        app.dependency_overrides[get_league_profile_repository] = lambda: mock_lp_repo
        with patch("routers.rankings._get_scoring_config", return_value=SCORING_CONFIG):
            resp = TestClient(app).post("/rankings/compute", json=COMPUTE_BODY).json()
        app.dependency_overrides.clear()
        assert resp["cached"] is True
        mock_proj_repo.get_by_season.assert_not_called()

    def test_missing_source_weights_returns_422(self, client: TestClient) -> None:
        body = {k: v for k, v in COMPUTE_BODY.items() if k != "source_weights"}
        assert client.post("/rankings/compute", json=body).status_code == 422

    def test_missing_scoring_config_id_returns_422(self, client: TestClient) -> None:
        body = {k: v for k, v in COMPUTE_BODY.items() if k != "scoring_config_id"}
        assert client.post("/rankings/compute", json=body).status_code == 422

    def test_all_zero_source_weights_returns_422(self, client: TestClient) -> None:
        # All weights = 0 is nonsensical — aggregation would divide by zero.
        # model_validator on RankingsComputeRequest rejects this → FastAPI returns 422.
        body = {**COMPUTE_BODY, "source_weights": {"dobber": 0, "hashtag": 0}}
        assert client.post("/rankings/compute", json=body).status_code == 422

    def test_empty_source_weights_returns_422(self, client: TestClient) -> None:
        # Empty dict is also invalid — no sources to aggregate.
        body = {**COMPUTE_BODY, "source_weights": {}}
        assert client.post("/rankings/compute", json=body).status_code == 422
```

- [ ] **Step 2: Run to verify they fail**

```bash
cd apps/api && pytest tests/routers/test_rankings.py -v
# Expected: FAIL
```

- [ ] **Step 3: Rewrite rankings router**

```python
# apps/api/routers/rankings.py
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from core.dependencies import (
    get_cache_service,
    get_current_user,
    get_league_profile_repository,
    get_projection_repository,
)
from models.schemas import RankedPlayer, RankingsComputeRequest, RankingsComputeResponse
from repositories.league_profiles import LeagueProfileRepository
from repositories.projections import ProjectionRepository
from services.cache import CacheService
from services.projections import aggregate_projections

router = APIRouter(prefix="/rankings", tags=["rankings"])


def _get_scoring_config(scoring_config_id: str) -> dict[str, float]:
    """Fetch scoring config stat_weights from DB.

    ⚠️  STUB — RANKINGS ARE NOT PRODUCTION-READY UNTIL THIS IS IMPLEMENTED.
    Every POST /rankings/compute call will return HTTP 501 until
    ScoringConfigRepository is built and injected here (see Known Follow-Ups).
    Replace this stub before any user-facing testing.

    Full implementation: inject ScoringConfigRepository, call
    repo.get(scoring_config_id) → return stat_weights dict, raise 404 if missing.
    """
    raise NotImplementedError("Inject ScoringConfigRepository to fetch scoring config")


@router.post("/compute", response_model=RankingsComputeResponse)
async def compute_rankings(
    req: RankingsComputeRequest,
    user: dict[str, Any] = Depends(get_current_user),
    proj_repo: ProjectionRepository = Depends(get_projection_repository),
    lp_repo: LeagueProfileRepository = Depends(get_league_profile_repository),
    cache: CacheService = Depends(get_cache_service),
) -> RankingsComputeResponse:
    # 1. Cache check
    cached_data = cache.get_rankings(
        req.season,
        req.source_weights,
        req.scoring_config_id,
        req.platform,
        req.league_profile_id,
    )
    if cached_data is not None:
        return RankingsComputeResponse(
            season=req.season,
            computed_at=datetime.now(UTC),
            cached=True,
            rankings=[RankedPlayer(**p) for p in cached_data],
        )

    # 2. Fetch scoring config
    try:
        scoring_config = _get_scoring_config(req.scoring_config_id)
    except NotImplementedError:
        raise HTTPException(status_code=501, detail="Scoring config lookup not yet implemented")
    except Exception:
        raise HTTPException(status_code=404, detail="Scoring config not found")

    # 3. Optionally fetch league profile for VORP
    league_profile: dict[str, Any] | None = None
    if req.league_profile_id:
        league_profile = lp_repo.get(req.league_profile_id, user["id"])
        if league_profile is None:
            raise HTTPException(
                status_code=403,
                detail="Not authorized to access this league profile",
            )

    # 4. Fetch projections and run pipeline
    rows = proj_repo.get_by_season(req.season, req.platform, user["id"])
    ranked = aggregate_projections(rows, req.source_weights, scoring_config, league_profile)

    # 5. Cache result
    cache.set_rankings(
        req.season,
        req.source_weights,
        req.scoring_config_id,
        req.platform,
        req.league_profile_id,
        ranked,
    )

    return RankingsComputeResponse(
        season=req.season,
        computed_at=datetime.now(UTC),
        cached=False,
        rankings=[RankedPlayer(**p) for p in ranked],
    )
```

- [ ] **Step 4: Add projection repository dependency**

In `apps/api/core/dependencies.py`, add:

```python
from repositories.projections import ProjectionRepository

def get_projection_repository() -> ProjectionRepository:
    return ProjectionRepository(get_db())
```

- [ ] **Step 5: Run rankings router tests**

```bash
cd apps/api && pytest tests/routers/test_rankings.py -v
# Expected: all pass (scoring config tests skip via patch)
```

- [ ] **Step 6: Run full test suite**

```bash
cd apps/api && pytest tests/ -v --tb=short
# Expected: all pass
```

- [ ] **Step 7: Commit**

```bash
git add routers/rankings.py tests/routers/test_rankings.py core/dependencies.py
git commit -m "feat(router): rewrite rankings/compute to use projection aggregation pipeline"
```

---

## Chunk 5: Exports Update

### Task 11: Update exports service for new output shape

**Files:**
- Modify: `apps/api/services/exports.py`
- Modify: `apps/api/tests/services/test_exports.py`

The export service now receives `RankedPlayer`-shaped dicts. Replace `composite_score`/`source_ranks` columns with `projected_fantasy_points`, `vorp`, `off_night_games`, and the full stat columns.

- [ ] **Step 1: Write failing tests for updated exports**

Replace `apps/api/tests/services/test_exports.py`:

```python
# apps/api/tests/services/test_exports.py
from __future__ import annotations

import io

import pytest
from unittest.mock import patch

from services.exports import generate_excel, generate_pdf


def _make_player(rank: int = 1, fp: float = 200.0) -> dict:
    return {
        "composite_rank": rank,
        "player_id": f"p{rank}",
        "name": "Connor McDavid",
        "team": "EDM",
        "default_position": "C",
        "platform_positions": ["C"],
        "projected_fantasy_points": fp,
        "vorp": 80.0,
        "schedule_score": 0.85,
        "off_night_games": 24,
        "source_count": 3,
        "projected_stats": {
            "g": 52, "a": 78, "plus_minus": 22, "pim": 28,
            "ppg": 18, "ppa": 24, "ppp": 32,
            "shg": None, "sha": None, "shp": None,
            "sog": 315, "fow": 820, "fol": 680,
            "hits": 45, "blocks": 32, "gp": 78,
            "gs": None, "w": None, "l": None, "ga": None,
            "sa": None, "sv": None, "sv_pct": None, "so": None, "otl": None,
        },
    }


class TestGenerateExcel:
    def test_returns_bytes(self) -> None:
        result = generate_excel([_make_player()], "2025-26")
        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_valid_xlsx_magic_bytes(self) -> None:
        result = generate_excel([_make_player()], "2025-26")
        # XLSX is a ZIP file — starts with PK magic bytes
        assert result[:2] == b"PK"

    def test_handles_empty_rankings(self) -> None:
        result = generate_excel([], "2025-26")
        assert isinstance(result, bytes)

    def test_null_stat_does_not_raise(self) -> None:
        player = _make_player()
        player["projected_stats"]["g"] = None
        result = generate_excel([player], "2025-26")
        assert isinstance(result, bytes)

    def test_null_fantasy_points_does_not_raise(self) -> None:
        player = _make_player()
        player["projected_fantasy_points"] = None
        result = generate_excel([player], "2025-26")
        assert isinstance(result, bytes)


class TestGeneratePdf:
    def test_returns_bytes(self) -> None:
        with patch("services.exports.HTML") as mock_html:
            mock_html.return_value.write_pdf.return_value = b"%PDF-fake"
            result = generate_pdf([_make_player()], "2025-26")
        assert isinstance(result, bytes)

    def test_null_stats_rendered_as_dash(self) -> None:
        player = _make_player()
        player["projected_stats"]["g"] = None
        html_content: list[str] = []
        with patch("services.exports.HTML") as mock_html:
            mock_html.return_value.write_pdf.return_value = b"%PDF-fake"
            mock_html.side_effect = lambda string: (
                html_content.append(string) or mock_html.return_value
            )
            generate_pdf([player], "2025-26")
        # The null g stat should appear as — in the HTML
        assert any("—" in s for s in html_content)
```

- [ ] **Step 2: Run to verify they fail**

```bash
cd apps/api && pytest tests/services/test_exports.py -v
# Expected: some fail (wrong column shapes, missing fields)
```

- [ ] **Step 3: Rewrite exports service**

```python
# apps/api/services/exports.py
"""
Export service — generates PDF and Excel files from projection-based rankings.

Input shape: list of RankedPlayer-compatible dicts (projected_stats, vorp, etc.)
"""
from __future__ import annotations

import io
from typing import Any

SKATER_STAT_LABELS = [
    ("gp", "GP"), ("g", "G"), ("a", "A"), ("plus_minus", "+/-"),
    ("pim", "PIM"), ("ppg", "PPG"), ("ppa", "PPA"), ("ppp", "PPP"),
    ("shg", "SHG"), ("sha", "SHA"), ("shp", "SHP"),
    ("sog", "SOG"), ("hits", "Hits"), ("blocks", "Blk"),
    ("fow", "FOW"), ("fol", "FOL"),
]
GOALIE_STAT_LABELS = [
    ("gs", "GS"), ("w", "W"), ("l", "L"), ("ga", "GA"),
    ("sa", "SA"), ("sv", "SV"), ("sv_pct", "SV%"), ("so", "SO"), ("otl", "OTL"),
]
ALL_STAT_LABELS = SKATER_STAT_LABELS + GOALIE_STAT_LABELS


def _fmt(val: Any) -> str:
    """Format a stat value: None → '—', float → rounded string."""
    if val is None:
        return "—"
    if isinstance(val, float):
        return f"{val:.3f}"
    return str(val)


def generate_excel(
    rankings: list[dict[str, Any]],
    season: str,
) -> bytes:
    """Return an Excel workbook as bytes."""
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    wb = Workbook()

    # ---- Sheet 1: Full Rankings ----
    ws = wb.active
    ws.title = "Full Rankings"

    header_fill = PatternFill(start_color="1E3A5F", end_color="1E3A5F", fill_type="solid")
    header_font = Font(color="FFFFFF", bold=True)

    stat_keys = [k for k, _ in ALL_STAT_LABELS]
    stat_header_labels = [label for _, label in ALL_STAT_LABELS]

    headers = [
        "ADP", "Taken", "Player", "Team", "Pos", "FanPts", "FP/GP",
        "VORP", "PRNK", "GP", "OFF",
    ] + stat_header_labels
    ws.append(headers)
    for cell in ws[1]:
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center")

    for row in rankings:
        stats = row.get("projected_stats", {})
        fp = row.get("projected_fantasy_points")
        gp = stats.get("gp")
        fp_per_gp = round(fp / gp, 2) if fp and gp else None
        stat_vals = [stats.get(k) for k in stat_keys]
        ws.append(
            [
                "",                                    # ADP placeholder
                "",                                    # TAKEN
                row.get("name", ""),
                row.get("team", ""),
                ", ".join(row.get("platform_positions") or [row.get("default_position", "")]),
                fp,
                fp_per_gp,
                row.get("vorp"),
                row.get("composite_rank"),
                gp,
                row.get("off_night_games"),
            ]
            + [v if v is not None else "" for v in stat_vals]
        )

    for col_idx in range(1, len(headers) + 1):
        ws.column_dimensions[get_column_letter(col_idx)].width = 10

    # ---- Sheet 2: Best Available ----
    ws2 = wb.create_sheet("Best Available")
    ws2.append(["Player", "Pos", "FanPts", "VORP"])
    for row in rankings:
        ws2.append([
            row.get("name", ""),
            ", ".join(row.get("platform_positions") or [row.get("default_position", "")]),
            row.get("projected_fantasy_points"),
            row.get("vorp"),
        ])

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


_HTML_TEMPLATE = """\
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8"/>
<style>
  body {{ font-family: Arial, sans-serif; font-size: 10px; margin: 15px; }}
  h1 {{ color: #1e3a5f; font-size: 16px; }}
  table {{ width: 100%; border-collapse: collapse; }}
  th {{ background: #1e3a5f; color: white; padding: 5px 6px; text-align: left; font-size: 9px; }}
  td {{ padding: 4px 6px; border-bottom: 1px solid #ddd; }}
  tr:nth-child(even) {{ background: #f4f7fb; }}
  .num {{ text-align: right; font-family: monospace; }}
  .rank {{ text-align: center; font-weight: bold; }}
  .chk {{ text-align: center; width: 20px; }}
</style>
</head>
<body>
<h1>PuckLogic Print &amp; Draft — {season}</h1>
<table>
  <thead><tr>
    <th class="chk">✓</th>
    <th>Rank</th><th>Player</th><th>Team</th><th>Pos</th>
    <th>FanPts</th><th>VORP</th><th>GP</th><th>OFF</th>
    {stat_headers}
  </tr></thead>
  <tbody>{rows}</tbody>
</table>
</body>
</html>
"""


def generate_pdf(
    rankings: list[dict[str, Any]],
    season: str,
) -> bytes:
    """Return a PDF as bytes. Requires WeasyPrint to be installed."""
    from weasyprint import HTML

    stat_headers = "".join(
        f"<th>{label}</th>" for _, label in ALL_STAT_LABELS
    )
    stat_keys = [k for k, _ in ALL_STAT_LABELS]

    rows_html = ""
    for row in rankings:
        stats = row.get("projected_stats", {})
        stat_cells = "".join(
            f"<td class='num'>{_fmt(stats.get(k))}</td>" for k in stat_keys
        )
        rows_html += (
            f"<tr>"
            f"<td class='chk'>☐</td>"
            f"<td class='rank'>{row.get('composite_rank', '')}</td>"
            f"<td>{row.get('name', '')}</td>"
            f"<td>{row.get('team', '')}</td>"
            f"<td>{', '.join(row.get('platform_positions') or [row.get('default_position', '')])}</td>"
            f"<td class='num'>{_fmt(row.get('projected_fantasy_points'))}</td>"
            f"<td class='num'>{_fmt(row.get('vorp'))}</td>"
            f"<td class='num'>{_fmt(stats.get('gp'))}</td>"
            f"<td class='num'>{_fmt(row.get('off_night_games'))}</td>"
            f"{stat_cells}"
            f"</tr>\n"
        )

    html_content = _HTML_TEMPLATE.format(
        season=season,
        stat_headers=stat_headers,
        rows=rows_html,
    )
    return HTML(string=html_content).write_pdf()
```

- [ ] **Step 4: Run export tests**

```bash
cd apps/api && pytest tests/services/test_exports.py -v
# Expected: all pass
```

- [ ] **Step 5: Run full test suite**

```bash
cd apps/api && pytest tests/ -v --tb=short
# Expected: all pass
```

- [ ] **Step 6: Commit**

```bash
git add services/exports.py tests/services/test_exports.py
git commit -m "feat(exports): update Excel and PDF generation for projection-based output shape"
```

---

## Chunk 6: Scoring Config CRUD + Double-Count Validation

> **Spec reference:** §1 (`scoring_configs`), §2 (PPP/PPG validation), §7.1 (source_weights key contract)
>
> This chunk removes the `_get_scoring_config` stub from the rankings router and replaces it with a real `ScoringConfigRepository` + CRUD router with PPP/PPG/PPA double-counting validation.

### Task 12: ScoringConfigRepository

**Files:**
- Create: `apps/api/repositories/scoring_configs.py`
- Create: `apps/api/tests/repositories/test_scoring_configs.py`

- [ ] **Step 1: Write failing tests**

```python
# apps/api/tests/repositories/test_scoring_configs.py
from __future__ import annotations

import pytest
from unittest.mock import MagicMock

from repositories.scoring_configs import ScoringConfigRepository

PRESET_ROW = {
    "id": "sc-1",
    "name": "Standard Points",
    "stat_weights": {"g": 3, "a": 2, "ppp": 1},
    "is_preset": True,
    "user_id": None,
    "created_at": "2026-03-01T00:00:00+00:00",
}
CUSTOM_ROW = {
    "id": "sc-2",
    "name": "My Custom",
    "stat_weights": {"g": 5, "a": 3},
    "is_preset": False,
    "user_id": "u-1",
    "created_at": "2026-03-01T00:00:00+00:00",
}


@pytest.fixture
def mock_db() -> MagicMock:
    return MagicMock()


@pytest.fixture
def repo(mock_db: MagicMock) -> ScoringConfigRepository:
    return ScoringConfigRepository(mock_db)


class TestList:
    def test_queries_scoring_configs(
        self, repo: ScoringConfigRepository, mock_db: MagicMock
    ) -> None:
        mock_db.table.return_value.select.return_value.or_.return_value.execute.return_value.data = []
        repo.list(user_id="u-1")
        mock_db.table.assert_called_once_with("scoring_configs")

    def test_returns_presets_and_user_configs(
        self, repo: ScoringConfigRepository, mock_db: MagicMock
    ) -> None:
        mock_db.table.return_value.select.return_value.or_.return_value.execute.return_value.data = [
            PRESET_ROW, CUSTOM_ROW
        ]
        result = repo.list(user_id="u-1")
        assert len(result) == 2


class TestGet:
    def test_returns_config_when_found(
        self, repo: ScoringConfigRepository, mock_db: MagicMock
    ) -> None:
        mock_db.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value.data = PRESET_ROW
        result = repo.get("sc-1")
        assert result == PRESET_ROW

    def test_returns_none_when_not_found(
        self, repo: ScoringConfigRepository, mock_db: MagicMock
    ) -> None:
        mock_db.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value.data = None
        assert repo.get("missing") is None


class TestCreate:
    def test_inserts_config(
        self, repo: ScoringConfigRepository, mock_db: MagicMock
    ) -> None:
        mock_db.table.return_value.insert.return_value.execute.return_value.data = [CUSTOM_ROW]
        result = repo.create({
            "name": "My Custom",
            "stat_weights": {"g": 5},
            "is_preset": False,
            "user_id": "u-1",
        })
        assert result == CUSTOM_ROW
```

- [ ] **Step 2: Run to verify they fail**

```bash
cd apps/api && pytest tests/repositories/test_scoring_configs.py -v
# Expected: FAIL — ModuleNotFoundError
```

- [ ] **Step 3: Implement ScoringConfigRepository**

```python
# apps/api/repositories/scoring_configs.py
from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from supabase import Client


class ScoringConfigRepository:
    def __init__(self, db: "Client") -> None:
        self._db = db

    def list(self, user_id: str) -> list[dict[str, Any]]:
        """Return all presets + this user's custom configs."""
        result = (
            self._db.table("scoring_configs")
            .select("*")
            .or_(f"is_preset.eq.true,user_id.eq.{user_id}")
            .execute()
        )
        return result.data

    def get(self, config_id: str) -> dict[str, Any] | None:
        result = (
            self._db.table("scoring_configs")
            .select("*")
            .eq("id", config_id)
            .maybe_single()
            .execute()
        )
        return result.data

    def create(self, data: dict[str, Any]) -> dict[str, Any]:
        result = self._db.table("scoring_configs").insert(data).execute()
        return result.data[0]
```

- [ ] **Step 4: Run tests**

```bash
cd apps/api && pytest tests/repositories/test_scoring_configs.py -v
# Expected: all pass
```

- [ ] **Step 5: Commit**

```bash
git add repositories/scoring_configs.py tests/repositories/test_scoring_configs.py
git commit -m "feat(repo): add ScoringConfigRepository"
```

---

### Task 13: Scoring config validation service

**Files:**
- Create: `apps/api/services/scoring_validation.py`
- Create: `apps/api/tests/services/test_scoring_validation.py`

PPP and PPG/PPA cannot both be non-zero in the same config. Same rule for SHP/SHG/SHA. This is enforced at config creation time.

- [ ] **Step 1: Write failing tests**

```python
# apps/api/tests/services/test_scoring_validation.py
from __future__ import annotations

import pytest

from services.scoring_validation import validate_scoring_config


class TestValidateScoringConfig:
    def test_valid_config_passes(self) -> None:
        # No conflict: ppp > 0, ppg and ppa are 0 (or absent)
        validate_scoring_config({"g": 3, "a": 2, "ppp": 1})

    def test_ppp_and_ppg_both_nonzero_raises(self) -> None:
        with pytest.raises(ValueError, match="PPP.*PPG"):
            validate_scoring_config({"ppp": 1, "ppg": 1})

    def test_ppp_and_ppa_both_nonzero_raises(self) -> None:
        with pytest.raises(ValueError, match="PPP.*PPA"):
            validate_scoring_config({"ppp": 1, "ppa": 1})

    def test_shp_and_shg_both_nonzero_raises(self) -> None:
        with pytest.raises(ValueError, match="SHP.*SHG"):
            validate_scoring_config({"shp": 1, "shg": 1})

    def test_shp_and_sha_both_nonzero_raises(self) -> None:
        with pytest.raises(ValueError, match="SHP.*SHA"):
            validate_scoring_config({"shp": 1, "sha": 1})

    def test_ppg_and_ppa_without_ppp_is_valid(self) -> None:
        # ppg + ppa are fine if ppp is 0 or absent
        validate_scoring_config({"ppg": 2, "ppa": 1})

    def test_ppp_zero_with_ppg_nonzero_is_valid(self) -> None:
        validate_scoring_config({"ppp": 0, "ppg": 2})

    def test_empty_config_is_valid(self) -> None:
        validate_scoring_config({})

    def test_shg_and_sha_without_shp_is_valid(self) -> None:
        validate_scoring_config({"shg": 2, "sha": 1})
```

- [ ] **Step 2: Run to verify they fail**

```bash
cd apps/api && pytest tests/services/test_scoring_validation.py -v
# Expected: FAIL — ModuleNotFoundError
```

- [ ] **Step 3: Implement validation**

```python
# apps/api/services/scoring_validation.py
"""Scoring config validation — enforces double-counting rules."""
from __future__ import annotations


def validate_scoring_config(stat_weights: dict[str, float]) -> None:
    """Raise ValueError if stat_weights double-counts PP or SH stats.

    Rules:
      - PPP and PPG/PPA cannot both be non-zero
      - SHP and SHG/SHA cannot both be non-zero
    """
    ppp = stat_weights.get("ppp", 0)
    ppg = stat_weights.get("ppg", 0)
    ppa = stat_weights.get("ppa", 0)
    shp = stat_weights.get("shp", 0)
    shg = stat_weights.get("shg", 0)
    sha = stat_weights.get("sha", 0)

    if ppp and ppg:
        raise ValueError(
            "Cannot score both PPP and PPG simultaneously — this double-counts power play goals"
        )
    if ppp and ppa:
        raise ValueError(
            "Cannot score both PPP and PPA simultaneously — this double-counts power play assists"
        )
    if shp and shg:
        raise ValueError(
            "Cannot score both SHP and SHG simultaneously — this double-counts short-handed goals"
        )
    if shp and sha:
        raise ValueError(
            "Cannot score both SHP and SHA simultaneously — this double-counts short-handed assists"
        )
```

- [ ] **Step 4: Run tests**

```bash
cd apps/api && pytest tests/services/test_scoring_validation.py -v
# Expected: all pass
```

- [ ] **Step 5: Commit**

```bash
git add services/scoring_validation.py tests/services/test_scoring_validation.py
git commit -m "feat(validation): add PPP/PPG and SHP/SHG double-counting validation"
```

---

### Task 14: Scoring config CRUD router

**Files:**
- Create: `apps/api/routers/scoring_configs.py`
- Create: `apps/api/tests/routers/test_scoring_configs.py`
- Modify: `apps/api/models/schemas.py` (add `ScoringConfigCreate`)
- Modify: `apps/api/core/dependencies.py` (add `get_scoring_config_repository`)
- Modify: `apps/api/main.py` (register router)

- [ ] **Step 1: Add ScoringConfigCreate schema to schemas.py**

Add after the existing `ScoringConfigOut` class:

```python
class ScoringConfigCreate(BaseModel):
    name: str
    stat_weights: dict[str, float]
```

- [ ] **Step 2: Write failing router tests**

```python
# apps/api/tests/routers/test_scoring_configs.py
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock

from main import app
from core.dependencies import get_current_user, get_scoring_config_repository

MOCK_USER = {"id": "u-1", "email": "test@example.com"}

PRESET_ROW = {
    "id": "sc-1",
    "name": "Standard Points",
    "stat_weights": {"g": 3, "a": 2, "ppp": 1},
    "is_preset": True,
}
CUSTOM_ROW = {
    "id": "sc-2",
    "name": "My Custom",
    "stat_weights": {"g": 5},
    "is_preset": False,
    "user_id": "u-1",
    "created_at": "2026-03-01T00:00:00+00:00",
}


@pytest.fixture
def mock_repo() -> MagicMock:
    repo = MagicMock()
    repo.list.return_value = [PRESET_ROW]
    repo.create.return_value = CUSTOM_ROW
    return repo


@pytest.fixture(autouse=True)
def override_deps(mock_repo: MagicMock) -> None:
    app.dependency_overrides[get_current_user] = lambda: MOCK_USER
    app.dependency_overrides[get_scoring_config_repository] = lambda: mock_repo
    yield
    app.dependency_overrides.clear()


class TestListScoringConfigs:
    def test_returns_200(self, client: TestClient) -> None:
        assert client.get("/scoring-configs").status_code == 200

    def test_returns_list(self, client: TestClient, mock_repo: MagicMock) -> None:
        mock_repo.list.return_value = [PRESET_ROW]
        data = client.get("/scoring-configs").json()
        assert isinstance(data, list)
        assert len(data) == 1

    def test_filters_by_user(self, client: TestClient, mock_repo: MagicMock) -> None:
        client.get("/scoring-configs")
        mock_repo.list.assert_called_once_with(user_id=MOCK_USER["id"])


class TestCreateScoringConfig:
    def test_returns_201(self, client: TestClient) -> None:
        body = {"name": "My Custom", "stat_weights": {"g": 5}}
        assert client.post("/scoring-configs", json=body).status_code == 201

    def test_ppp_ppg_double_count_returns_400(self, client: TestClient) -> None:
        body = {"name": "Bad", "stat_weights": {"ppp": 1, "ppg": 1}}
        resp = client.post("/scoring-configs", json=body)
        assert resp.status_code == 400
        assert "PPP" in resp.json()["detail"]

    def test_shp_shg_double_count_returns_400(self, client: TestClient) -> None:
        body = {"name": "Bad", "stat_weights": {"shp": 1, "shg": 1}}
        resp = client.post("/scoring-configs", json=body)
        assert resp.status_code == 400

    def test_valid_config_calls_create(self, client: TestClient, mock_repo: MagicMock) -> None:
        body = {"name": "My Custom", "stat_weights": {"g": 5}}
        client.post("/scoring-configs", json=body)
        mock_repo.create.assert_called_once()

    def test_sets_user_id_and_is_preset_false(self, client: TestClient, mock_repo: MagicMock) -> None:
        body = {"name": "My Custom", "stat_weights": {"g": 5}}
        client.post("/scoring-configs", json=body)
        call_data = mock_repo.create.call_args.args[0]
        assert call_data["user_id"] == MOCK_USER["id"]
        assert call_data["is_preset"] is False
```

- [ ] **Step 3: Run to verify they fail**

```bash
cd apps/api && pytest tests/routers/test_scoring_configs.py -v
# Expected: FAIL
```

- [ ] **Step 4: Implement scoring_configs router**

```python
# apps/api/routers/scoring_configs.py
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from core.dependencies import get_current_user, get_scoring_config_repository
from models.schemas import ScoringConfigCreate, ScoringConfigOut
from repositories.scoring_configs import ScoringConfigRepository
from services.scoring_validation import validate_scoring_config

router = APIRouter(prefix="/scoring-configs", tags=["scoring-configs"])


@router.get("", response_model=list[ScoringConfigOut])
async def list_scoring_configs(
    user: dict[str, Any] = Depends(get_current_user),
    repo: ScoringConfigRepository = Depends(get_scoring_config_repository),
) -> list[ScoringConfigOut]:
    return repo.list(user_id=user["id"])


@router.post("", response_model=ScoringConfigOut, status_code=201)
async def create_scoring_config(
    body: ScoringConfigCreate,
    user: dict[str, Any] = Depends(get_current_user),
    repo: ScoringConfigRepository = Depends(get_scoring_config_repository),
) -> ScoringConfigOut:
    try:
        validate_scoring_config(body.stat_weights)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    row = repo.create({
        **body.model_dump(),
        "user_id": user["id"],
        "is_preset": False,
    })
    return ScoringConfigOut(**row)
```

- [ ] **Step 5: Add dependency + register router**

In `apps/api/core/dependencies.py`, add:

```python
from repositories.scoring_configs import ScoringConfigRepository

def get_scoring_config_repository() -> ScoringConfigRepository:
    return ScoringConfigRepository(get_db())
```

In `apps/api/main.py`, add:

```python
from routers import (
    exports, health, league_profiles, rankings, scoring_configs, sources, stripe, user_kits
)
# ...
app.include_router(scoring_configs.router)
```

- [ ] **Step 6: Run tests**

```bash
cd apps/api && pytest tests/routers/test_scoring_configs.py -v
# Expected: all pass
```

- [ ] **Step 7: Commit**

```bash
git add routers/scoring_configs.py tests/routers/test_scoring_configs.py \
        repositories/scoring_configs.py models/schemas.py \
        core/dependencies.py main.py
git commit -m "feat(scoring-configs): add CRUD router with PPP/SHP double-counting validation"
```

---

### Task 15: Wire ScoringConfigRepository into rankings router

Remove the `_get_scoring_config` stub and inject the real repository.

**Files:**
- Modify: `apps/api/routers/rankings.py`
- Modify: `apps/api/tests/routers/test_rankings.py`

- [ ] **Step 1: Update rankings router**

In `apps/api/routers/rankings.py`:

1. Remove the `_get_scoring_config` stub function entirely.
2. Add `ScoringConfigRepository` dependency:

```python
from core.dependencies import (
    get_cache_service,
    get_current_user,
    get_league_profile_repository,
    get_projection_repository,
    get_scoring_config_repository,
)
from repositories.scoring_configs import ScoringConfigRepository
```

3. Add parameter to the route handler:

```python
@router.post("/compute", response_model=RankingsComputeResponse)
async def compute_rankings(
    req: RankingsComputeRequest,
    user: dict[str, Any] = Depends(get_current_user),
    proj_repo: ProjectionRepository = Depends(get_projection_repository),
    lp_repo: LeagueProfileRepository = Depends(get_league_profile_repository),
    sc_repo: ScoringConfigRepository = Depends(get_scoring_config_repository),
    cache: CacheService = Depends(get_cache_service),
) -> RankingsComputeResponse:
```

4. Replace the `_get_scoring_config` call block with:

```python
    # 2. Fetch scoring config
    sc_row = sc_repo.get(req.scoring_config_id)
    if sc_row is None:
        raise HTTPException(status_code=404, detail="Scoring config not found")
    scoring_config = sc_row["stat_weights"]
```

- [ ] **Step 2: Update ranking router tests**

In `apps/api/tests/routers/test_rankings.py`:

1. Remove the `patch("routers.rankings._get_scoring_config", ...)` context manager.
2. Add a `mock_sc_repo` fixture:

```python
from core.dependencies import get_scoring_config_repository

SCORING_CONFIG_ROW = {
    "id": "sc-1",
    "name": "Standard",
    "stat_weights": {"g": 3.0, "a": 2.0},
    "is_preset": True,
    "user_id": None,
}

@pytest.fixture
def mock_sc_repo() -> MagicMock:
    repo = MagicMock()
    repo.get.return_value = SCORING_CONFIG_ROW
    return repo
```

3. Add `mock_sc_repo` to the `client` fixture and override `get_scoring_config_repository`:

```python
@pytest.fixture
def client(
    mock_proj_repo: MagicMock,
    mock_cache: MagicMock,
    mock_lp_repo: MagicMock,
    mock_sc_repo: MagicMock,
) -> TestClient:
    app.dependency_overrides[get_current_user] = lambda: MOCK_USER
    app.dependency_overrides[get_projection_repository] = lambda: mock_proj_repo
    app.dependency_overrides[get_cache_service] = lambda: mock_cache
    app.dependency_overrides[get_league_profile_repository] = lambda: mock_lp_repo
    app.dependency_overrides[get_scoring_config_repository] = lambda: mock_sc_repo
    yield TestClient(app)
    app.dependency_overrides.clear()
```

4. Add a test for missing scoring config:

```python
    def test_missing_scoring_config_returns_404(
        self, mock_sc_repo: MagicMock, mock_proj_repo: MagicMock,
        mock_cache: MagicMock, mock_lp_repo: MagicMock,
    ) -> None:
        mock_sc_repo.get.return_value = None
        app.dependency_overrides[get_current_user] = lambda: MOCK_USER
        app.dependency_overrides[get_projection_repository] = lambda: mock_proj_repo
        app.dependency_overrides[get_cache_service] = lambda: mock_cache
        app.dependency_overrides[get_league_profile_repository] = lambda: mock_lp_repo
        app.dependency_overrides[get_scoring_config_repository] = lambda: mock_sc_repo
        resp = TestClient(app).post("/rankings/compute", json=COMPUTE_BODY)
        app.dependency_overrides.clear()
        assert resp.status_code == 404
```

- [ ] **Step 3: Run tests**

```bash
cd apps/api && pytest tests/routers/test_rankings.py -v
# Expected: all pass
```

- [ ] **Step 4: Commit**

```bash
git add routers/rankings.py tests/routers/test_rankings.py
git commit -m "feat(router): wire ScoringConfigRepository into rankings/compute, remove stub"
```

---

## Chunk 7: Gap Fixes (SCAN invalidation, source key validation, VORP UTIL/BN, exports router)

> **Spec references:** §7.1 (source_weights key validation), §7.3 (UTIL/BN exclusion from VORP), §7.4 (SCAN-based invalidation)

### Task 16: SCAN-based cache invalidation

**Files:**
- Modify: `apps/api/services/cache.py`
- Modify: `apps/api/tests/services/test_cache.py`

The current `invalidate_rankings` uses `KEYS` which blocks Redis. Replace with cursor-based `SCAN` + batched deletes.

- [ ] **Step 1: Write failing test for SCAN-based invalidation**

Add to `apps/api/tests/services/test_cache.py`:

```python
class TestInvalidateRankingsWithScan:
    def test_uses_scan_not_keys(
        self, cache_with_redis: CacheService, mock_redis: MagicMock
    ) -> None:
        # scan_iter should be called instead of keys
        mock_redis.scan_iter.return_value = iter(["rankings:2025-26:abc"])
        cache_with_redis.invalidate_rankings("2025-26")
        mock_redis.scan_iter.assert_called_once()
        mock_redis.keys.assert_not_called()

    def test_deletes_in_batches(
        self, cache_with_redis: CacheService, mock_redis: MagicMock
    ) -> None:
        # 250 keys → 3 batches of 100, 100, 50
        fake_keys = [f"rankings:2025-26:{i:064d}" for i in range(250)]
        mock_redis.scan_iter.return_value = iter(fake_keys)
        cache_with_redis.invalidate_rankings("2025-26")
        assert mock_redis.delete.call_count == 3

    def test_no_keys_means_no_delete(
        self, cache_with_redis: CacheService, mock_redis: MagicMock
    ) -> None:
        mock_redis.scan_iter.return_value = iter([])
        cache_with_redis.invalidate_rankings("2025-26")
        mock_redis.delete.assert_not_called()
```

- [ ] **Step 2: Run to verify they fail**

```bash
cd apps/api && pytest tests/services/test_cache.py::TestInvalidateRankingsWithScan -v
# Expected: FAIL — scan_iter not called
```

- [ ] **Step 3: Update invalidate_rankings**

In `apps/api/services/cache.py`, replace the `invalidate_rankings` method:

```python
    _INVALIDATE_BATCH_SIZE = 100

    def invalidate_rankings(self, season: str) -> None:
        """Delete all cached rankings for a season using cursor-based SCAN.

        Uses SCAN (not KEYS) to avoid blocking Redis on large keyspaces.
        Deletes in batches of 100 keys.
        """
        if not self._client:
            return
        try:
            pattern = f"rankings:{season}:*"
            batch: list[str] = []
            for key in self._client.scan_iter(match=pattern, count=self._INVALIDATE_BATCH_SIZE):
                batch.append(key)
                if len(batch) >= self._INVALIDATE_BATCH_SIZE:
                    self._client.delete(*batch)
                    batch = []
            if batch:
                self._client.delete(*batch)
        except Exception as exc:
            logger.warning("Cache invalidate failed: %s", exc)
```

- [ ] **Step 4: Update old invalidation test**

In `apps/api/tests/services/test_cache.py`, remove or update the existing `test_invalidate_calls_keys_then_delete` and `test_invalidate_skips_delete_when_no_keys` tests to use `scan_iter` instead of `keys`:

```python
    def test_invalidate_calls_scan_iter_with_pattern(
        self, cache_with_redis: CacheService, mock_redis: MagicMock
    ) -> None:
        mock_redis.scan_iter.return_value = iter(["rankings:2025-26:abc123"])
        cache_with_redis.invalidate_rankings(SEASON)
        mock_redis.scan_iter.assert_called_once_with(
            match=f"rankings:{SEASON}:*", count=100
        )

    def test_invalidate_skips_delete_when_no_keys(
        self, cache_with_redis: CacheService, mock_redis: MagicMock
    ) -> None:
        mock_redis.scan_iter.return_value = iter([])
        cache_with_redis.invalidate_rankings(SEASON)
        mock_redis.delete.assert_not_called()
```

- [ ] **Step 5: Run cache tests**

```bash
cd apps/api && pytest tests/services/test_cache.py -v
# Expected: all pass
```

- [ ] **Step 6: Commit**

```bash
git add services/cache.py tests/services/test_cache.py
git commit -m "fix(cache): use SCAN-based invalidation instead of KEYS"
```

---

### Task 17: Source weights key validation

**Files:**
- Modify: `apps/api/routers/rankings.py`
- Modify: `apps/api/tests/routers/test_rankings.py`

Unknown source keys in `source_weights` must be rejected with HTTP 400.

- [ ] **Step 1: Write failing test**

Add to `apps/api/tests/routers/test_rankings.py`:

```python
class TestSourceWeightsValidation:
    def test_unknown_source_key_returns_400(
        self, mock_proj_repo: MagicMock, mock_cache: MagicMock,
        mock_lp_repo: MagicMock, mock_sc_repo: MagicMock,
    ) -> None:
        # Source repo returns no source matching "ghost_source"
        mock_source_repo = MagicMock()
        mock_source_repo.get_by_name.return_value = None
        app.dependency_overrides[get_current_user] = lambda: MOCK_USER
        app.dependency_overrides[get_projection_repository] = lambda: mock_proj_repo
        app.dependency_overrides[get_cache_service] = lambda: mock_cache
        app.dependency_overrides[get_league_profile_repository] = lambda: mock_lp_repo
        app.dependency_overrides[get_scoring_config_repository] = lambda: mock_sc_repo
        app.dependency_overrides[get_source_repository] = lambda: mock_source_repo
        body = {**COMPUTE_BODY, "source_weights": {"ghost_source": 10}}
        resp = TestClient(app).post("/rankings/compute", json=body)
        app.dependency_overrides.clear()
        assert resp.status_code == 400
        assert "ghost_source" in resp.json()["detail"]

    def test_inaccessible_source_key_returns_400(
        self, mock_proj_repo: MagicMock, mock_cache: MagicMock,
        mock_lp_repo: MagicMock, mock_sc_repo: MagicMock,
    ) -> None:
        # Source exists but belongs to another user
        mock_source_repo = MagicMock()
        mock_source_repo.get_by_name.return_value = {
            "name": "other_custom", "user_id": "other-user-99",
        }
        app.dependency_overrides[get_current_user] = lambda: MOCK_USER
        app.dependency_overrides[get_projection_repository] = lambda: mock_proj_repo
        app.dependency_overrides[get_cache_service] = lambda: mock_cache
        app.dependency_overrides[get_league_profile_repository] = lambda: mock_lp_repo
        app.dependency_overrides[get_scoring_config_repository] = lambda: mock_sc_repo
        app.dependency_overrides[get_source_repository] = lambda: mock_source_repo
        body = {**COMPUTE_BODY, "source_weights": {"other_custom": 10}}
        resp = TestClient(app).post("/rankings/compute", json=body)
        app.dependency_overrides.clear()
        assert resp.status_code == 400
        assert "other_custom" in resp.json()["detail"]
```

- [ ] **Step 2: Run to verify they fail**

```bash
cd apps/api && pytest tests/routers/test_rankings.py::TestSourceWeightsValidation -v
# Expected: FAIL — no validation yet, returns 200
```

- [ ] **Step 3: Add validation to rankings router**

In `apps/api/routers/rankings.py`, add `get_source_repository` to imports, add `SourceRepository` dependency, and insert validation between cache check and scoring config fetch:

```python
from core.dependencies import (
    get_cache_service,
    get_current_user,
    get_league_profile_repository,
    get_projection_repository,
    get_scoring_config_repository,
    get_source_repository,
)
from repositories.sources import SourceRepository

# In the route handler, add the dependency:
    src_repo: SourceRepository = Depends(get_source_repository),

# After cache check, before scoring config fetch, add:
    # 1b. Validate source_weights keys
    for key in req.source_weights:
        source = src_repo.get_by_name(key)
        if source is None:
            raise HTTPException(status_code=400, detail=f"Unknown source key: {key}")
        # Check accessibility: user's own sources or system sources
        source_uid = source.get("user_id")
        if source_uid is not None and source_uid != user["id"]:
            raise HTTPException(status_code=400, detail=f"Unknown source key: {key}")
```

- [ ] **Step 4: Run tests**

```bash
cd apps/api && pytest tests/routers/test_rankings.py -v
# Expected: all pass
```

- [ ] **Step 5: Commit**

```bash
git add routers/rankings.py tests/routers/test_rankings.py
git commit -m "feat(router): validate source_weights keys against sources table"
```

---

### Task 18: VORP — exclude UTIL and BN from replacement-level math

**Files:**
- Modify: `apps/api/services/projections.py`
- Modify: `apps/api/tests/services/test_projections.py`

Per spec §7.3, only positional starter slots (C, LW, RW, D, G) count for replacement-level thresholds. The existing `compute_vorp` already works correctly because it looks up `roster_slots.get(pos, 0)` by the player's NHL canonical position — and no player has `default_position = "UTIL"` or `"BN"`. This task adds a defensive guard and explicit test to document the invariant.

- [ ] **Step 1: Write test**

Add to `TestComputeVorp` in `apps/api/tests/services/test_projections.py`:

```python
    def test_util_and_bn_excluded_from_replacement_level(self) -> None:
        """UTIL and BN roster slots must not inflate replacement-level thresholds.

        Defensive: no real player has default_position="UTIL" or "BN", but
        roster_slots may contain these keys. compute_vorp must only use
        positional starter slots (C, LW, RW, D, G) for threshold calculation.
        """
        players = self._make_players([100.0, 90.0, 80.0])
        # roster_slots includes UTIL and BN — they should be ignored
        profile = {
            "num_teams": 1,
            "roster_slots": {"C": 1, "UTIL": 2, "BN": 4},
        }
        result = compute_vorp(players, profile)
        # replacement level uses C=1 slot only: threshold = 1*1+1 = rank 2 (index 1) = 90
        assert result["p0"] == pytest.approx(10.0)
```

- [ ] **Step 2: Run test to verify it passes (defensive — should already pass)**

```bash
cd apps/api && pytest tests/services/test_projections.py::TestComputeVorp::test_util_and_bn_excluded_from_replacement_level -v
# Expected: PASS (existing code handles this correctly by design)
```

- [ ] **Step 3: Add defensive guard to compute_vorp**

In `apps/api/services/projections.py`, in `compute_vorp`, add a constant and filter as defensive programming. This ensures correctness even if unexpected position values appear:

```python
# At module level, add:
_VORP_POSITION_SLOTS = frozenset({"C", "LW", "RW", "D", "G"})

# In compute_vorp, when reading roster_slots, change:
        slots = roster_slots.get(pos, 0)
# To:
        if pos not in _VORP_POSITION_SLOTS:
            result[pid] = None
            continue
        slots = roster_slots.get(pos, 0)
```

- [ ] **Step 4: Run tests**

```bash
cd apps/api && pytest tests/services/test_projections.py::TestComputeVorp -v
# Expected: all pass
```

- [ ] **Step 5: Commit**

```bash
git add services/projections.py tests/services/test_projections.py
git commit -m "fix(vorp): exclude UTIL and BN slots from replacement-level calculation"
```

---

### Task 19: Update exports router for new pipeline

**Files:**
- Modify: `apps/api/routers/exports.py`
- Modify: `apps/api/tests/routers/test_exports.py`

The exports router still uses the old rank-based pipeline. It must use the new `ExportRequest` schema (with `source_weights`, `scoring_config_id`, `platform`, `league_profile_id`) and call `aggregate_projections`.

- [ ] **Step 1: Write failing tests**

Replace `apps/api/tests/routers/test_exports.py`:

```python
# apps/api/tests/routers/test_exports.py
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from main import app
from core.dependencies import (
    get_current_user,
    get_league_profile_repository,
    get_projection_repository,
    get_scoring_config_repository,
)

MOCK_USER = {"id": "u-1", "email": "test@example.com"}

SCORING_CONFIG_ROW = {
    "id": "sc-1",
    "name": "Standard",
    "stat_weights": {"g": 3.0, "a": 2.0},
    "is_preset": True,
    "user_id": None,
}

DB_ROW = {
    "player_id": "p1",
    "season": "2025-26",
    "g": 50, "a": 45,
    "plus_minus": None, "pim": None, "ppg": None, "ppa": None, "ppp": None,
    "shg": None, "sha": None, "shp": None, "sog": None, "fow": None,
    "fol": None, "hits": None, "blocks": None, "gp": 82,
    "gs": None, "w": None, "l": None, "ga": None, "sa": None,
    "sv": None, "sv_pct": None, "so": None, "otl": None,
    "sources": {"name": "dobber", "is_paid": False, "user_id": None},
    "players": {"name": "McDavid", "team": "EDM", "position": "C"},
    "player_platform_positions": [{"positions": ["C"]}],
    "schedule_scores": [],
}

EXCEL_BODY = {
    "season": "2025-26",
    "source_weights": {"dobber": 10},
    "scoring_config_id": "sc-1",
    "platform": "espn",
    "export_type": "excel",
}
PDF_BODY = {**EXCEL_BODY, "export_type": "pdf"}


@pytest.fixture
def mock_proj_repo() -> MagicMock:
    repo = MagicMock()
    repo.get_by_season.return_value = [DB_ROW]
    return repo


@pytest.fixture
def mock_sc_repo() -> MagicMock:
    repo = MagicMock()
    repo.get.return_value = SCORING_CONFIG_ROW
    return repo


@pytest.fixture
def mock_lp_repo() -> MagicMock:
    repo = MagicMock()
    repo.get.return_value = None
    return repo


@pytest.fixture(autouse=True)
def override_deps(
    mock_proj_repo: MagicMock,
    mock_sc_repo: MagicMock,
    mock_lp_repo: MagicMock,
) -> None:
    app.dependency_overrides[get_current_user] = lambda: MOCK_USER
    app.dependency_overrides[get_projection_repository] = lambda: mock_proj_repo
    app.dependency_overrides[get_scoring_config_repository] = lambda: mock_sc_repo
    app.dependency_overrides[get_league_profile_repository] = lambda: mock_lp_repo
    yield
    app.dependency_overrides.clear()


class TestGenerateExcelExport:
    def test_returns_200(self, client: TestClient) -> None:
        with patch("routers.exports.generate_excel", return_value=b"XLSX"):
            assert client.post("/exports/generate", json=EXCEL_BODY).status_code == 200

    def test_content_type_is_xlsx(self, client: TestClient) -> None:
        with patch("routers.exports.generate_excel", return_value=b"XLSX"):
            resp = client.post("/exports/generate", json=EXCEL_BODY)
        assert "spreadsheetml" in resp.headers["content-type"]


class TestGeneratePdfExport:
    def test_returns_200(self, client: TestClient) -> None:
        with patch("routers.exports.generate_pdf", return_value=b"%PDF"):
            assert client.post("/exports/generate", json=PDF_BODY).status_code == 200

    def test_content_type_is_pdf(self, client: TestClient) -> None:
        with patch("routers.exports.generate_pdf", return_value=b"%PDF"):
            resp = client.post("/exports/generate", json=PDF_BODY)
        assert resp.headers["content-type"] == "application/pdf"


class TestExportValidation:
    def test_invalid_export_type_returns_422(self, client: TestClient) -> None:
        body = {**EXCEL_BODY, "export_type": "csv"}
        assert client.post("/exports/generate", json=body).status_code == 422

    def test_missing_scoring_config_id_returns_422(self, client: TestClient) -> None:
        body = {k: v for k, v in EXCEL_BODY.items() if k != "scoring_config_id"}
        assert client.post("/exports/generate", json=body).status_code == 422

    def test_missing_scoring_config_returns_404(
        self, client: TestClient, mock_sc_repo: MagicMock
    ) -> None:
        mock_sc_repo.get.return_value = None
        resp = client.post("/exports/generate", json=EXCEL_BODY)
        assert resp.status_code == 404


class TestAuthRequired:
    @pytest.fixture(autouse=True)
    def reject_auth(self) -> None:
        app.dependency_overrides[get_current_user] = lambda: (_ for _ in ()).throw(
            HTTPException(status_code=401, detail="Unauthorized")
        )
        yield

    def test_unauthenticated_returns_401(self, client: TestClient) -> None:
        assert client.post("/exports/generate", json=EXCEL_BODY).status_code == 401
```

- [ ] **Step 2: Run to verify they fail**

```bash
cd apps/api && pytest tests/routers/test_exports.py -v
# Expected: FAIL — old imports and pipeline
```

- [ ] **Step 3: Rewrite exports router**

```python
# apps/api/routers/exports.py
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

from core.dependencies import (
    get_current_user,
    get_league_profile_repository,
    get_projection_repository,
    get_scoring_config_repository,
    get_source_repository,
)
from models.schemas import ExportRequest
from repositories.league_profiles import LeagueProfileRepository
from repositories.projections import ProjectionRepository
from repositories.scoring_configs import ScoringConfigRepository
from repositories.sources import SourceRepository
from services.exports import generate_excel, generate_pdf
from services.projections import aggregate_projections

router = APIRouter(prefix="/exports", tags=["exports"])


@router.post("/generate")
async def generate_export(
    req: ExportRequest,
    user: dict[str, Any] = Depends(get_current_user),
    proj_repo: ProjectionRepository = Depends(get_projection_repository),
    sc_repo: ScoringConfigRepository = Depends(get_scoring_config_repository),
    lp_repo: LeagueProfileRepository = Depends(get_league_profile_repository),
    src_repo: SourceRepository = Depends(get_source_repository),
) -> Response:
    """Compute projection-based rankings and stream as PDF or Excel."""
    # Validate source_weights keys (same rules as POST /rankings/compute)
    for key in req.source_weights:
        source = src_repo.get_by_name(key)
        if source is None:
            raise HTTPException(status_code=400, detail=f"Unknown source key: {key}")
        source_uid = source.get("user_id")
        if source_uid is not None and source_uid != user["id"]:
            raise HTTPException(status_code=400, detail=f"Unknown source key: {key}")

    # Fetch scoring config
    sc_row = sc_repo.get(req.scoring_config_id)
    if sc_row is None:
        raise HTTPException(status_code=404, detail="Scoring config not found")

    # Optionally fetch league profile for VORP
    league_profile: dict[str, Any] | None = None
    if req.league_profile_id:
        league_profile = lp_repo.get(req.league_profile_id, user["id"])
        if league_profile is None:
            raise HTTPException(status_code=403, detail="Not authorized to access this league profile")

    # Run projection pipeline
    rows = proj_repo.get_by_season(req.season, req.platform, user["id"])
    ranked = aggregate_projections(
        rows, req.source_weights, sc_row["stat_weights"], league_profile
    )

    filename = f"pucklogic-rankings-{req.season}"

    if req.export_type == "excel":
        content = generate_excel(ranked, req.season)
        return Response(
            content=content,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="{filename}.xlsx"'},
        )

    content = generate_pdf(ranked, req.season)
    return Response(
        content=content,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}.pdf"'},
    )
```

- [ ] **Step 4: Run tests**

```bash
cd apps/api && pytest tests/routers/test_exports.py -v
# Expected: all pass
```

- [ ] **Step 5: Run full test suite**

```bash
cd apps/api && pytest tests/ -v --tb=short
# Expected: all pass
```

- [ ] **Step 6: Commit**

```bash
git add routers/exports.py tests/routers/test_exports.py
git commit -m "feat(exports): rewrite exports router to use projection aggregation pipeline"
```

---

## Chunk 8: Frontend Updates

### Task 20: Update TypeScript types

**Files:**
- Modify: `apps/web/src/types/index.ts`

- [ ] **Step 1: Replace types**

Replace the contents of `apps/web/src/types/index.ts`:

```typescript
/** Shared TypeScript types for PuckLogic — used by web app and (eventually) extension. */

export interface Source {
  id: string;
  name: string;
  display_name: string;
  url: string | null;
  active: boolean;
  default_weight: number | null;
  is_paid: boolean;
}

export interface ProjectedStats {
  g: number | null;
  a: number | null;
  plus_minus: number | null;
  pim: number | null;
  ppg: number | null;
  ppa: number | null;
  ppp: number | null;
  shg: number | null;
  sha: number | null;
  shp: number | null;
  sog: number | null;
  fow: number | null;
  fol: number | null;
  hits: number | null;
  blocks: number | null;
  gp: number | null;
  gs: number | null;
  w: number | null;
  l: number | null;
  ga: number | null;
  sa: number | null;
  sv: number | null;
  sv_pct: number | null;
  so: number | null;
  otl: number | null;
}

export interface RankedPlayer {
  composite_rank: number;
  player_id: string;
  name: string;
  team: string | null;
  default_position: string | null;
  platform_positions: string[];
  projected_fantasy_points: number | null;
  vorp: number | null;
  schedule_score: number | null;
  off_night_games: number | null;
  source_count: number;
  projected_stats: ProjectedStats;
  breakout_score: number | null;
  regression_risk: number | null;
}

export interface RankingsResult {
  season: string;
  computed_at: string;
  cached: boolean;
  rankings: RankedPlayer[];
}

export interface ComputeRankingsRequest {
  season: string;
  source_weights: Record<string, number>;
  scoring_config_id: string;
  platform: string;
  league_profile_id?: string | null;
}

export interface ScoringConfig {
  id: string;
  name: string;
  stat_weights: Record<string, number>;
  is_preset: boolean;
}

export interface LeagueProfile {
  id: string;
  name: string;
  platform: string;
  num_teams: number;
  roster_slots: Record<string, number>;
  scoring_config_id: string;
  created_at: string;
}

export interface UserKit {
  id: string;
  name: string;
  source_weights: Record<string, number>;
  created_at: string;
}

export type WeightsMap = Record<string, number>;
```

- [ ] **Step 2: Commit**

```bash
git add apps/web/src/types/index.ts
git commit -m "feat(types): update TypeScript types for projection-based pipeline"
```

---

### Task 21: Update API client

**Files:**
- Modify: `apps/web/src/lib/api/rankings.ts`

- [ ] **Step 1: Update computeRankings request shape**

```typescript
// apps/web/src/lib/api/rankings.ts
import type { ComputeRankingsRequest, RankingsResult } from "@/types";
import { apiFetch } from "./index";

export async function computeRankings(req: ComputeRankingsRequest): Promise<RankingsResult> {
  return apiFetch<RankingsResult>("/rankings/compute", {
    method: "POST",
    body: JSON.stringify(req),
  });
}
```

> Note: The `ComputeRankingsRequest` type now includes `source_weights` (renamed from `weights`), `scoring_config_id`, `platform`, and optional `league_profile_id`. Callers (dashboard page, store actions) must be updated to pass these fields.

- [ ] **Step 2: Commit**

```bash
git add apps/web/src/lib/api/rankings.ts
git commit -m "feat(api-client): update computeRankings for new request shape"
```

---

### Task 22: Update Zustand store

**Files:**
- Modify: `apps/web/src/store/slices/rankings.ts`

- [ ] **Step 1: Update rankings slice to include new request fields**

The store slice's `computeRankings` action must now accept and pass `scoring_config_id`, `platform`, and optionally `league_profile_id`. Update the slice state and action accordingly.

Specific changes depend on the current store implementation — the slice must construct a `ComputeRankingsRequest` with all required fields and call the updated `computeRankings` API function.

- [ ] **Step 2: Run frontend tests**

```bash
cd apps/web && pnpm test
# Expected: some tests may need updates for new request shape
```

- [ ] **Step 3: Fix any broken tests**

Update test mocks and assertions to use `source_weights` (not `weights`) and include `scoring_config_id`, `platform`.

- [ ] **Step 4: Commit**

```bash
git add apps/web/src/store/slices/rankings.ts
git commit -m "feat(store): update rankings slice for projection-based request"
```

---

## Final Verification

- [ ] **Run full backend test suite**

```bash
cd apps/api && pytest tests/ -v --tb=short
# Expected: all pass, no skipped
```

- [ ] **Run full frontend test suite**

```bash
cd apps/web && pnpm test
# Expected: all pass
```

- [ ] **Verify migration file count**

```bash
ls supabase/migrations/
# Expected: 001_initial_schema.sql  002_projection_aggregation.sql
```

- [ ] **Open PR**

Use `commit-commands:commit-push-pr` skill. PR description must include:
1. Summary of all changes (migration, schemas, services, repos, cache, routers, exports, frontend types)
2. Test plan: `cd apps/api && pytest tests/ -v` and `cd apps/web && pnpm test`
3. Follow-up items from the table below

---

## Known Follow-Ups (not in scope for this plan)

| Item | Notes |
|------|-------|
| `GET /rankings/sources` | List available projection sources with weights. Currently returns old data from `SourceRepository`. |
| Platform position filter in repo | PostgREST join filter on `player_platform_positions.platform` may need a Supabase RPC — verify with actual client. |
| NHL.com / MoneyPuck scraper migration | Update `BaseScraper.scrape()` return value: was "rows upserted to player_rankings", now should write to `player_stats`. |
| First concrete `BaseProjectionScraper` | HashtagHockey scraper is highest priority (most reliable free projection source). |
| `schedule_scores` ingestion job | GitHub Actions job pulling NHL schedule API, computing off-night counts. |
| `player_platform_positions` ingestion | Per-platform position eligibility for ESPN, Yahoo, Fantrax. |
| Source `default_weight` in `SourceOut` schema | Add `default_weight` and `is_paid` to `SourceOut` Pydantic model + frontend `Source` type. |
| Dashboard page update | `apps/web/src/app/dashboard/page.tsx` needs scoring config selector, platform dropdown, and league profile picker. |
| `RankingsTable` component rewrite | Update to display `projected_fantasy_points`, `vorp`, stat columns instead of `composite_score` and `source_ranks`. |
