from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api import agents, conversations, runs, stats, telegram, workflows
from app.config import settings
from app.db import SessionLocal, init_db
from app.integrations.telegram_bot import start_polling, stop_polling
from app.schemas.contract import Health
from app.seed import seed_if_empty
from app.websocket import router as websocket_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.validate_startup()
    await init_db()
    async with SessionLocal() as db:
        await seed_if_empty(db)
    await start_polling()
    yield
    await stop_polling()


app = FastAPI(title="Agent Mesh API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(agents.router, prefix="/api/v1")
app.include_router(workflows.router, prefix="/api/v1")
app.include_router(runs.router, prefix="/api/v1")
app.include_router(conversations.router, prefix="/api/v1")
app.include_router(telegram.router, prefix="/api/v1")
app.include_router(stats.router, prefix="/api/v1")
app.include_router(websocket_router)


@app.get("/health", response_model=Health)
async def health() -> Health:
    async with SessionLocal() as db:
        await db.execute(text("SELECT 1"))
    return Health(status="ok", db="ok")
