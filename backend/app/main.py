"""
RAG Backend API - FastAPI Application
端口: 8002
"""
import os
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from config import UPLOAD_DIR

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting RAG Backend API … port 8002")
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    yield
    logger.info("Shutting down RAG Backend API …")


app = FastAPI(
    title="RAG Platform API",
    description="RAG document retrieval and Q&A API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files for uploads
os.makedirs(UPLOAD_DIR, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

# Health check
@app.get("/health", tags=["meta"])
def health():
    return {"status": "ok", "service": "rag-backend", "version": app.version}

# API Routes
from app.api import rag
app.include_router(rag.router, prefix="/rag", tags=["rag"])
