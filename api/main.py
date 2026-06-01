"""
FastAPI backend — wraps the existing scripts/ pipeline and exposes HTTP endpoints.

Run with:
    uvicorn api.main:app --reload --port 8000
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.routers.search import router as search_router

app = FastAPI(title="Species Synonym API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

app.include_router(search_router)