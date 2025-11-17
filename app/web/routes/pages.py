from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.core.config import settings
from app.core.cookies import SESSION_COOKIE_NAME
from app.core import i18n

router = APIRouter()
templates = Jinja2Templates(directory="app/web/templates")
templates.env.globals.setdefault("SESSION_COOKIE_NAME", SESSION_COOKIE_NAME)
templates.env.globals.setdefault("ENABLE_CSRF_JSON", settings.ENABLE_CSRF_JSON)
templates.env.globals.setdefault("_", i18n.gettext_proxy)


@router.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Display home page."""
    return templates.TemplateResponse("index.html", {"request": request})



@router.get("/set-lang")
async def set_language(request: Request, lang: str | None = None):
    """Set the language cookie and redirect back to referer (or home).

    Example: /set-lang?lang=pt
    """
    # Normalize param from querystring
    chosen = lang or request.query_params.get("lang")
    if chosen:
        # Map common short codes to our locale identifiers
        if chosen.lower().startswith("pt"):
            cookie_val = "pt_BR"
        else:
            cookie_val = "en"
    else:
        cookie_val = "en"

    redirect_to = request.headers.get("referer") or "/"
    from fastapi.responses import RedirectResponse

    resp = RedirectResponse(url=redirect_to, status_code=303)
    # Set long-lived cookie
    resp.set_cookie("lang", cookie_val, max_age=10 * 365 * 24 * 3600, path="/")
    return resp


@router.get("/privacidade", response_class=HTMLResponse)
async def privacy(request: Request):
    """Privacy policy page."""
    return templates.TemplateResponse("pages/privacidade.html", {"request": request})


@router.get("/termos", response_class=HTMLResponse)
async def terms(request: Request):
    """Terms of use page."""
    return templates.TemplateResponse("pages/termos.html", {"request": request})
