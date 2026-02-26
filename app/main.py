from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings  # noqa: F401


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown events.

    ML models and background tasks (e.g. email polling) will be
    initialised here during the hackathon.
    """
    # --- startup ---
    yield
    # --- shutdown ---


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


@app.get("/health")
async def health_check():
    return {"status": "ok"}
