#!/usr/bin/env python3
"""Minimal test server for batch research endpoints."""
import os
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
# Import directly to avoid __init__.py issues
from app.routers.batch_research import router as batch_research_router

app = FastAPI(title="Batch Research Test Server", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(batch_research_router)

@app.get("/")
async def root():
    return {"message": "Batch Research API", "docs": "/docs", "endpoints": [
        "POST /api/research/start-batch",
        "GET /api/research/job/{job_id}",
        "GET /api/research/job/{job_id}/report",
        "GET /api/research/job/{job_id}/markdown",
        "GET /api/research/job/{job_id}/evidence",
    ]}

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8002"))
    uvicorn.run(app, host="127.0.0.1", port=port, reload=True)

