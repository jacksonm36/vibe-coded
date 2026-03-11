"""Ansible Control Panel - FastAPI app and static serving."""
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.database import init_db
from app.api import projects, inventories, credentials, job_templates, jobs

app = FastAPI(
    title="Ansible Control Panel",
    description="Red Hat–style Ansible web UI with database storage",
    version="0.1.0",
)

# Ensure we're running from project root for static/data paths
ROOT = Path(__file__).resolve().parent.parent
os.chdir(ROOT)

# API routes
app.include_router(projects.router)
app.include_router(inventories.router)
app.include_router(credentials.router)
app.include_router(job_templates.router)
app.include_router(jobs.router)

# Static files (frontend)
static_dir = ROOT / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.on_event("startup")
def startup():
    init_db()


@app.get("/")
def index():
    """Serve SPA."""
    index_file = static_dir / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return {"message": "Ansible Control Panel API", "docs": "/docs"}
