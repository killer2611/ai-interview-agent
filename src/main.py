"""FastAPI application entry point (Phase 1)."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from src.api.routes import router
from src.config import settings
from src.services.curriculum_engine import CurriculumEngine
from src.services.llm_provider import LLMProvider
from src.services.session_store import SessionStore

logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

# Shared service instances
curriculum_engine = CurriculumEngine()
session_store = SessionStore()
llm_provider = LLMProvider()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context manager loading curriculum at startup."""
    curriculum_path = Path(settings.curriculum_path)
    if not curriculum_path.is_absolute():
        curriculum_path = Path(__file__).parent.parent / curriculum_path

    logger.info("Loading curriculum from %s", curriculum_path)
    curriculum_engine.load(curriculum_path)
    logger.info(
        "Curriculum loaded successfully: %d modules, %d days",
        curriculum_engine.total_modules,
        curriculum_engine.total_days,
    )
    yield
    logger.info("Shutdown complete. Active sessions: %d", session_store.count)


from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI(
    title="The Interview Agent",
    description="AI-powered adaptive technical interview system",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


frontend_path = Path(__file__).parent.parent / "frontend"
if frontend_path.exists():
    app.mount("/static", StaticFiles(directory=frontend_path), name="static")

    @app.get("/")
    async def serve_demo():
        """Serve the lightweight Phase 6 demo frontend."""
        return FileResponse(frontend_path / "index.html")


@app.get("/health")
async def health_check():
    """Health check endpoint exposing system status."""
    return {
        "status": "ok",
        "curriculum_loaded": curriculum_engine.total_days > 0,
        "total_days": curriculum_engine.total_days,
        "total_modules": curriculum_engine.total_modules,
        "active_sessions": session_store.count,
    }

