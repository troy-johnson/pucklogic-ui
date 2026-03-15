"""
Pydantic request/response schemas for Phase 2 endpoints.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, model_validator

# ---------------------------------------------------------------------------
# Sources
# ---------------------------------------------------------------------------


class SourceOut(BaseModel):
    id: str
    name: str
    display_name: str
    url: str | None = None
    active: bool


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
    def source_weights_not_all_zero(self) -> RankingsComputeRequest:
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
    l: int | None = None  # noqa: E741
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


class ScoringConfigCreate(BaseModel):
    name: str
    stat_weights: dict[str, float]


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
    def source_weights_not_all_zero(self) -> ExportRequest:
        if not self.source_weights or all(v == 0 for v in self.source_weights.values()):
            raise ValueError("source_weights: at least one source must have a non-zero weight")
        return self


class ExportJobResponse(BaseModel):
    job_id: str
    status: str
    download_url: str | None = None


# ---------------------------------------------------------------------------
# Stripe
# ---------------------------------------------------------------------------


class CheckoutSessionRequest(BaseModel):
    success_url: str
    cancel_url: str
    user_id: str | None = None


class CheckoutSessionResponse(BaseModel):
    checkout_url: str
    session_id: str


# ---------------------------------------------------------------------------
# User Kit (saved weight configs — source-weight presets only)
# ---------------------------------------------------------------------------


class UserKitCreate(BaseModel):
    name: str
    source_weights: dict[str, float]


class UserKitOut(BaseModel):
    id: str
    name: str
    source_weights: dict[str, float]
    created_at: datetime
