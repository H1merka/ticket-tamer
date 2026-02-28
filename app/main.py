from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import tickets, knowledge_base, export


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown events.

    Initialises APScheduler for KB cleanup and email polling.
    """
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from app.database import async_session_factory
    from app.services.kb_cleanup_service import cleanup_expired_chunks

    scheduler = AsyncIOScheduler()

    # KB cleanup — runs every KB_CLEANUP_INTERVAL_H hours
    async def _run_cleanup():
        async with async_session_factory() as db:
            await cleanup_expired_chunks(db, dry_run=False)

    scheduler.add_job(
        _run_cleanup,
        "interval",
        hours=settings.kb_cleanup_interval_h,
        id="kb_cleanup",
        replace_existing=True,
    )

    scheduler.start()
    app.state.scheduler = scheduler

    # --- startup ---
    yield
    # --- shutdown ---
    scheduler.shutdown(wait=False)


app = FastAPI(
    title="Ticket Tamer",
    description="AI agent for automating technical support email processing",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(tickets.router)
app.include_router(knowledge_base.router)
app.include_router(export.router)


@app.get("/health")
async def health_check():
    return {"status": "ok"}
