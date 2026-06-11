"""
FastAPI backend — wraps the existing scripts/ pipeline and exposes HTTP endpoints.

Run with:
    uvicorn api.main:app --reload --port 8000
"""

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.routers.search import router as search_router
from api.routers.taxonomy import router as taxonomy_router

app = FastAPI(title="Species Synonym API")

# Comma-separated list of allowed frontend origins. Defaults to local dev; set
# ALLOWED_ORIGINS on the host (e.g. a Hugging Face Space variable) to add the
# deployed Vercel URL — no code change needed.
_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000")
allow_origins = [o.strip() for o in _origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_methods=["GET"],
    allow_headers=["*"],
)

app.include_router(search_router)
app.include_router(taxonomy_router)