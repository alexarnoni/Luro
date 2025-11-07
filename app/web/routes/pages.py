from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.core.config import settings
from app.core.cookies import SESSION_COOKIE_NAME

router = APIRouter()
templates = Jinja2Templates(directory="app/web/templates")
templates.env.globals.setdefault("SESSION_COOKIE_NAME", SESSION_COOKIE_NAME)
templates.env.globals.setdefault("ENABLE_CSRF_JSON", settings.ENABLE_CSRF_JSON)


@router.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Display home page."""
    return templates.TemplateResponse("index.html", {"request": request})
