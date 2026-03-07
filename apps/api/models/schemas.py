"""
Pydantic request/response schemas for Phase 2 endpoints.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

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
# Rankings
# ---------------------------------------------------------------------------


class RankingsComputeRequest(BaseModel):
    season: str = Field(..., examples=["2025-26"])
    weights: dict[str, float] = Field(
        ...,
        description="Source name → weight (0–100). Weights need not sum to 100; "
        "they are normalised internally.",
        examples=[{"nhl_com": 40, "moneypuck": 30, "natural_stat_trick": 30}],
    )


class RankedPlayer(BaseModel):
    composite_rank: int
    composite_score: float
    player_id: str
    name: str
    team: str | None = None
    position: str | None = None
    source_ranks: dict[str, int] = Field(
        default_factory=dict,
        description="Individual rank per source for transparency.",
    )


class RankingsComputeResponse(BaseModel):
    season: str
    computed_at: datetime
    cached: bool
    rankings: list[RankedPlayer]


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
# Exports
# ---------------------------------------------------------------------------


class ExportRequest(BaseModel):
    season: str
    weights: dict[str, float]
    export_type: str = Field(..., pattern="^(pdf|excel)$")


class ExportJobResponse(BaseModel):
    job_id: str
    status: str
    download_url: str | None = None


# ---------------------------------------------------------------------------
# User Kit (saved weight configs)
# ---------------------------------------------------------------------------


class UserKitCreate(BaseModel):
    name: str
    season: str
    weights: dict[str, float]


class UserKitOut(BaseModel):
    id: str
    name: str
    season: str
    weights: dict[str, float]
    created_at: datetime
