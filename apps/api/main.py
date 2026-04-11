import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.config import settings
from core.dependencies import get_db
from ml.loader import ModelNotAvailableError, load
from routers import (
    auth,
    draft_sessions,
    exports,
    health,
    league_profiles,
    players,
    rankings,
    scoring_configs,
    sources,
    stripe,
    user_kits,
)
from routers import trends as trends_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """FastAPI lifespan — load ML models at startup.

    On success: app.state.models = (breakout_model, regression_model)
    On failure: app.state.models = None  (GET /trends returns 503)

    Failure modes that set models=None:
    - Supabase Storage unreachable
    - ml-artifacts bucket or artifact files missing
    - Deserialization error

    This is NOT a startup crash — the API starts normally.
    503 on /trends is the signal to ops that retraining hasn't run yet
    or Storage is misconfigured.
    """
    try:
        db = get_db()
        breakout_model, regression_model = load(db=db, season=settings.current_season)
        app.state.models = (breakout_model, regression_model)
        logger.info("ML models loaded for season %s", settings.current_season)
    except ModelNotAvailableError as exc:
        app.state.models = None
        logger.warning(
            "ML models not available for season %s: %s — GET /trends will return 503",
            settings.current_season,
            exc,
        )

    yield
    # Shutdown: nothing to clean up


app = FastAPI(
    title="PuckLogic API",
    version="0.1.0",
    docs_url="/docs" if not settings.is_production else None,
    redoc_url="/redoc" if not settings.is_production else None,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=(
        [settings.frontend_url] if settings.is_production else ["http://localhost:3000"]
    ),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(draft_sessions.router)
app.include_router(health.router)
app.include_router(players.router)
app.include_router(sources.router)
app.include_router(rankings.router)
app.include_router(exports.router)
app.include_router(stripe.router)
app.include_router(user_kits.router)
app.include_router(league_profiles.router)
app.include_router(scoring_configs.router)
app.include_router(trends_router.router)
