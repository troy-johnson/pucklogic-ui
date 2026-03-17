from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.config import settings
from routers import (
    auth,
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

app = FastAPI(
    title="PuckLogic API",
    version="0.1.0",
    docs_url="/docs" if not settings.is_production else None,
    redoc_url="/redoc" if not settings.is_production else None,
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
app.include_router(health.router)
app.include_router(players.router)
app.include_router(sources.router)
app.include_router(rankings.router)
app.include_router(exports.router)
app.include_router(stripe.router)
app.include_router(user_kits.router)
app.include_router(league_profiles.router)
app.include_router(scoring_configs.router)
