from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.routes.documents import router as documents_router
from app.core.config import settings
from app.core.database import init_db
from app.core.logging import setup_logging

setup_logging()

app = FastAPI(
    title="Intelligent Document Intelligence Platform",
    description="API for document extraction, validation, and storage",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(documents_router, prefix="/api/v1")

@app.on_event("startup")
def startup() -> None:
    init_db()

@app.get("/api/v1/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "document-intelligence"}

@app.get("/api/v1")
def api_root() -> dict[str, str]:
    return {
        "service": "document-intelligence",
        "status": "ok",
        "docs": "/docs",
        "health": "/api/v1/health",
    }

frontend_dir = Path(__file__).resolve().parents[2] / "frontend"
app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")
