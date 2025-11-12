from __future__ import annotations
from pathlib import Path
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, HTMLResponse
from starlette.templating import Jinja2Templates
from ..services.stats import StatsService


router = APIRouter(tags=["dashboard"])
# Template directory relative to backend/app
template_dir = Path(__file__).parent.parent / "templates"
templates = Jinja2Templates(directory=str(template_dir))

# Add static_url function to templates
def static_url(request, path: str) -> str:
    """Generate URL for static files."""
    base_url = str(request.base_url).rstrip('/')
    return f"{base_url}/{path.lstrip('/')}"

templates.env.globals["static_url"] = static_url


@router.get("/api/dashboard", response_class=JSONResponse)
async def api_dashboard():
    return await StatsService.compute()


@router.get("/dashboard", response_class=HTMLResponse)
async def view_dashboard(request: Request):
    stats = await StatsService.compute()
    return templates.TemplateResponse("dashboard.html", {"request": request, "stats": stats})

