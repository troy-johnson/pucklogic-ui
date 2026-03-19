"""
Pydantic request/response schemas for Phase 2 and Phase 3 endpoints.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, StrictBool, computed_field, model_validator

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
    "g",
    "a",
    "plus_minus",
    "pim",
    "ppg",
    "ppa",
    "ppp",
    "shg",
    "sha",
    "shp",
    "sog",
    "fow",
    "fol",
    "hits",
    "blocks",
    "gp",
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
    export_type: str = Field(..., pattern="^(pdf|excel)$")

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


# ---------------------------------------------------------------------------
# Players
# ---------------------------------------------------------------------------


class PlayerOut(BaseModel):
    id: str
    name: str
    team: str | None = None
    position: str | None = None
    nhl_id: int | None = None


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=1)


class RefreshRequest(BaseModel):
    refresh_token: str


class AuthUserOut(BaseModel):
    id: str
    email: str


class AuthResponse(BaseModel):
    access_token: str
    refresh_token: str
    user: AuthUserOut


# ---------------------------------------------------------------------------
# Custom source upload
# ---------------------------------------------------------------------------


class UnmatchedPlayer(BaseModel):
    row_number: int
    original_name: str
    closest_match: str | None = None
    match_score: float | None = None


class CustomSourceOut(BaseModel):
    id: str
    name: str
    display_name: str
    player_count: int
    season: str
    created_at: datetime


class UploadResponse(BaseModel):
    source_id: str
    rows_upserted: int
    unmatched: list[UnmatchedPlayer]
    slots_used: int
    slots_total: int = 2  # Must match FREE_SLOT_LIMIT in routers/sources.py


# ---------------------------------------------------------------------------
# Trends — Phase 3 Layer 1 ML scores (GET /trends)
# No paywall gate in v1.0; all scores visible to free users.
# Layer 2 columns (trending_up_score etc.) added in v2.0.
# ---------------------------------------------------------------------------

# Canonical type aliases — match the SQL CHECK constraints in 003_phase3_ml_features.sql
ProjectionTier = Literal["HIGH", "MEDIUM", "LOW"]
SkaterPosition = Literal["C", "LW", "RW", "D", "G"]


class ShapValues(BaseModel):
    """Per-feature SHAP contributions for breakout and regression models.

    Both dicts must not be simultaneously empty — use shap_values=None on TrendedPlayer
    when SHAP has not been computed for a player.
    """

    breakout: dict[str, float] = Field(default_factory=dict)
    regression: dict[str, float] = Field(default_factory=dict)

    @model_validator(mode="after")
    def at_least_one_shap_entry(self) -> ShapValues:
        if not self.breakout and not self.regression:
            raise ValueError(
                "ShapValues must contain at least one entry in breakout or regression; "
                "use shap_values=None on TrendedPlayer if SHAP was not computed."
            )
        return self


class TrendedPlayer(BaseModel):
    player_id: str
    name: str
    position: SkaterPosition | None = None
    team: str | None = None
    # Probability scores — validated to [0, 1] range; values outside range indicate ML bug
    breakout_score: float | None = Field(None, ge=0.0, le=1.0)
    regression_risk: float | None = Field(None, ge=0.0, le=1.0)
    confidence: float | None = Field(None, ge=0.0, le=1.0)
    projection_tier: ProjectionTier | None = None
    projection_pts: float | None = None
    # Signal dicts: keys are signal names, values are strict booleans (int 0/1 not accepted)
    breakout_signals: dict[str, StrictBool] | None = None
    regression_signals: dict[str, StrictBool] | None = None
    # shap_top3: each inner list is exactly [feature_name: str, shap_value: float] (2 elements)
    shap_top3: dict[str, list[list[str | float]]] | None = None
    shap_values: ShapValues | None = None  # full per-feature SHAP (may be large)


class TrendsResponse(BaseModel):
    season: str
    # None when no player_trends rows exist for this season yet (check has_trends first)
    updated_at: datetime | None = None
    # True when player_trends rows exist for this season; False = model not yet run
    has_trends: bool
    players: list[TrendedPlayer]

    @model_validator(mode="after")
    def updated_at_required_when_has_trends(self) -> TrendsResponse:
        if self.has_trends and self.updated_at is None:
            raise ValueError(
                "updated_at must be set when has_trends=True; "
                "the ML pipeline must record when scores were written."
            )
        return self

    @computed_field  # type: ignore[misc]
    @property
    def player_count(self) -> int:
        """Always consistent with len(players) — do not pass separately."""
        return len(self.players)
