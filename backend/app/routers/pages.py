from __future__ import annotations
from pathlib import Path
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from starlette.templating import Jinja2Templates

router = APIRouter(tags=["pages"])
template_dir = Path(__file__).parent.parent / "templates"
templates = Jinja2Templates(directory=str(template_dir))

# Add static_url function to templates
def static_url(request, path: str) -> str:
    """Generate URL for static files."""
    base_url = str(request.base_url).rstrip('/')
    return f"{base_url}/{path.lstrip('/')}"

templates.env.globals["static_url"] = static_url


@router.get("/chat", response_class=HTMLResponse)
async def chat_page(request: Request):
    """Archive Detective chat interface."""
    return templates.TemplateResponse("chat.html", {"request": request})


@router.get("/desk", response_class=HTMLResponse)
async def desk_page(request: Request):
    """Research desk interface."""
    return templates.TemplateResponse("desk.html", {"request": request})


@router.get("/collections", response_class=HTMLResponse)
async def collections_page(request: Request):
    """Collections board."""
    return templates.TemplateResponse("collections.html", {"request": request})


@router.get("/studio", response_class=HTMLResponse)
async def studio_page(request: Request):
    """Report studio."""
    return templates.TemplateResponse("studio.html", {"request": request})


@router.get("/timeline", response_class=HTMLResponse)
async def timeline_page(request: Request):
    """Timeline view."""
    return templates.TemplateResponse("timeline.html", {"request": request})


@router.get("/status", response_class=HTMLResponse)
async def status_page(request: Request):
    """System status page."""
    return templates.TemplateResponse("status.html", {"request": request})


@router.get("/notebook", response_class=HTMLResponse)
async def notebook_page(request: Request):
    """Research notebook page with entity extraction and timelines."""
    return templates.TemplateResponse("notebook.html", {"request": request})


@router.get("/report", response_class=HTMLResponse)
async def report_page(request: Request):
    """Deep Research Report Generator page."""
    return templates.TemplateResponse("report.html", {"request": request})

