from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api import agents, auth as auth_router, conversations, runs, stats, telegram, workflows
from app.auth import get_current_user
from app.config import settings
from app.db import SessionLocal, init_db
from app.integrations.telegram_bot import start_polling, stop_polling
from app.scheduler import start as start_scheduler, stop as stop_scheduler
from app.schemas.contract import Health
from app.seed import seed_if_empty
from app.websocket import router as websocket_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.validate_startup()
    await init_db()
    async with SessionLocal() as db:
        await seed_if_empty(db)
    await start_scheduler()
    await start_polling()
    yield
    await stop_polling()
    await stop_scheduler()


app = FastAPI(title="Agent Mesh API", version="0.1.0", lifespan=lifespan)

_cors_origins = [origin.strip() for origin in settings.CORS_ALLOW_ORIGINS.split(",") if origin.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Public routers (no auth dependency).
app.include_router(auth_router.router, prefix="/api/v1")
app.include_router(telegram.router, prefix="/api/v1")  # webhook signed by Telegram, not user

# Protected routers — gated by get_current_user when AUTH_USERNAME is set.
_auth_dep = [Depends(get_current_user)]
app.include_router(agents.router, prefix="/api/v1", dependencies=_auth_dep)
app.include_router(workflows.router, prefix="/api/v1", dependencies=_auth_dep)
app.include_router(runs.router, prefix="/api/v1", dependencies=_auth_dep)
app.include_router(conversations.router, prefix="/api/v1", dependencies=_auth_dep)
app.include_router(stats.router, prefix="/api/v1", dependencies=_auth_dep)
app.include_router(websocket_router)


@app.get("/health", response_model=Health)
async def health() -> Health:
    async with SessionLocal() as db:
        await db.execute(text("SELECT 1"))
    return Health(status="ok", db="ok")
