from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.routers import tickets, knowledge_base, export, analytics, auth


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

    # Email polling — runs every 60 seconds
    async def _poll_emails():
        from agent.pipeline import process_email
        from app.services.email_service import fetch_new_emails

        emails = await fetch_new_emails()
        if not emails:
            return
        async with async_session_factory() as db:
            for em in emails:
                try:
                    await process_email(
                        db,
                        email_from=em.sender,
                        subject=em.subject,
                        body=em.body,
                        message_id=em.message_id,
                        attachments=em.attachments,
                        email_to=em.recipient,
                    )
                except Exception:
                    import logging
                    logging.getLogger(__name__).exception(
                        "Pipeline error for message %s", em.message_id
                    )

    scheduler.add_job(
        _poll_emails,
        "interval",
        seconds=60,
        id="email_poll",
        max_instances=1,
        replace_existing=True,
    )

    # Crawler — crawl eriskip.com periodically
    async def _run_crawler():
        from agent.crawler import crawl_eriskip
        try:
            await crawl_eriskip()
        except Exception:
            import logging
            logging.getLogger(__name__).exception(
                "Crawler job failed"
            )

    scheduler.add_job(
        _run_crawler,
        "interval",
        hours=settings.crawler_interval_h,
        id="eriskip_crawler",
        max_instances=1,
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
app.include_router(auth.router)
app.include_router(tickets.router)
app.include_router(knowledge_base.router)
app.include_router(export.router)
app.include_router(analytics.router)


@app.get("/health")
async def health_check():
    return {"status": "ok"}


# Serve built frontend SPA from /app/static (Docker image)
_STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
if _STATIC_DIR.is_dir():
    app.mount("/assets", StaticFiles(directory=_STATIC_DIR / "assets"), name="static-assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        """Serve SPA index.html for all non-API routes."""
        file = _STATIC_DIR / full_path
        if file.is_file():
            return FileResponse(file)
        return FileResponse(_STATIC_DIR / "index.html")
