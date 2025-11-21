from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import html
import logging
import resend

from app.core.config import settings
from app.core.cookies import SESSION_COOKIE_NAME
from app.core import i18n
from app.core.database import get_db
from app.domain.users.models import User

router = APIRouter()
templates = Jinja2Templates(directory="app/web/templates")
templates.env.globals.setdefault("SESSION_COOKIE_NAME", SESSION_COOKIE_NAME)
templates.env.globals.setdefault("ENABLE_CSRF_JSON", settings.ENABLE_CSRF_JSON)
templates.env.globals.setdefault("_", i18n.gettext_proxy)
templates.env.globals.setdefault("ASSETS_VERSION", settings.ASSETS_VERSION)
templates.env.globals.setdefault(
    "is_admin",
    lambda user: bool(user and getattr(user, "email", None) and user.email.lower() in settings.admin_emails),
)

logger = logging.getLogger(__name__)

FEEDBACK_TYPES = {
    "praise": "Elogio",
    "suggestion": "Sugestão",
    "bug": "Bug/Problema",
    "other": "Outro",
}


async def _get_optional_user(request: Request, db: AsyncSession) -> User | None:
    """Return the logged user or None (based on the session cookie)."""
    session_email = request.cookies.get(SESSION_COOKIE_NAME)
    if not session_email:
        return None
    result = await db.execute(select(User).where(User.email == session_email))
    return result.scalar_one_or_none()


def _build_resend_from_field() -> str:
    """Normalize the From field for Resend, mirroring auth logic."""
    import re

    from_raw = (settings.RESEND_FROM_EMAIL or "").strip()
    EMAIL_RE = re.compile(r"^[^@<>\s]+@[^@<>\s]+\.[^@<>\s]+$")
    NAME_EMAIL_RE = re.compile(r"^.+ <[^@<>\s]+@[^@<>\s]+\.[^@<>\s]+>$")

    if EMAIL_RE.match(from_raw):
        return f"{settings.APP_NAME} <{from_raw}>"
    if NAME_EMAIL_RE.match(from_raw):
        return from_raw

    logger.warning("RESEND_FROM_EMAIL value '%s' is invalid; falling back to noreply", from_raw)
    return f"{settings.APP_NAME} <noreply@example.com>"


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


@router.get("/feedback", response_class=HTMLResponse)
async def feedback_form(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Render feedback form."""
    user = await _get_optional_user(request, db)
    initial_kind = request.query_params.get("type") or "suggestion"
    form_state = {
        "email": getattr(user, "email", None) or "",
        "kind": initial_kind if initial_kind in FEEDBACK_TYPES else "suggestion",
        "subject": "",
        "message": "",
    }
    return templates.TemplateResponse(
        "pages/feedback.html",
        {"request": request, "user": user, "form": form_state, "feedback_types": FEEDBACK_TYPES, "errors": [], "success": None},
    )


@router.post("/feedback", response_class=HTMLResponse)
async def submit_feedback(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Handle feedback submission and dispatch email via Resend."""
    user = await _get_optional_user(request, db)
    form = await request.form()

    email = (form.get("email") or "").strip()
    kind = (form.get("kind") or "suggestion").strip()
    subject = (form.get("subject") or "").strip()
    message = (form.get("message") or "").strip()

    if not email and user and getattr(user, "email", None):
        email = user.email.strip()

    errors: list[str] = []
    if kind not in FEEDBACK_TYPES:
        kind = "suggestion"
    if not message or len(message) < 5:
        errors.append("Mensagem é obrigatória (mínimo 5 caracteres).")
    if email and "@" not in email:
        errors.append("E-mail inválido.")
    if not settings.RESEND_API_KEY:
        errors.append("Envio indisponível: configure RESEND_API_KEY.")
    if not settings.FEEDBACK_TO_EMAIL:
        errors.append("Envio indisponível: configure FEEDBACK_TO_EMAIL.")

    form_state = {
        "email": email,
        "kind": kind,
        "subject": subject,
        "message": message,
    }

    success = None
    if not errors:
        try:
            resend.api_key = settings.RESEND_API_KEY
            from_field = _build_resend_from_field()
            to_email = settings.FEEDBACK_TO_EMAIL

            safe_subject = subject or f"Feedback ({FEEDBACK_TYPES[kind]})"
            client_ip = request.client.host if request.client else "unknown"
            ua = request.headers.get("user-agent", "")
            session_email = request.cookies.get(SESSION_COOKIE_NAME) or ""
            safe_message = html.escape(message).replace("\n", "<br>")
            safe_subject_html = html.escape(safe_subject)
            safe_email_html = html.escape(email or "(não informado)")
            safe_session_email = html.escape(session_email or "(não informado)")
            ua_html = html.escape(ua or "")
            kind_label = html.escape(FEEDBACK_TYPES[kind])

            body = f"""
            <html>
            <body>
                <h2>Novo feedback recebido</h2>
                <p><strong>Tipo:</strong> {kind_label}</p>
                <p><strong>Assunto:</strong> {safe_subject_html}</p>
                <p><strong>Email informado:</strong> {safe_email_html}</p>
                <p><strong>Usuário (cookie):</strong> {safe_session_email}</p>
                <p><strong>IP:</strong> {html.escape(client_ip)}</p>
                <p><strong>User-Agent:</strong> {ua_html}</p>
                <hr>
                <p><strong>Mensagem:</strong><br>{safe_message}</p>
            </body>
            </html>
            """

            resend.Emails.send({
                "from": from_field,
                "to": to_email,
                "subject": f"[Feedback] {safe_subject}",
                "html": body,
            })
            logger.info("Feedback enviado com sucesso (tipo=%s, email=%s, ip=%s)", kind, email or "anon", client_ip)
            success = "Feedback enviado! Obrigado por compartilhar."
            form_state["message"] = ""
            form_state["subject"] = ""
        except Exception as exc:  # noqa: BLE001
            logger.error("Erro ao enviar feedback", exc_info=exc)
            errors.append("Não foi possível enviar o feedback agora. Tente novamente em instantes.")

    status_code = 200 if success else (400 if errors else 200)
    return templates.TemplateResponse(
        "pages/feedback.html",
        {
            "request": request,
            "user": user,
            "form": form_state,
            "feedback_types": FEEDBACK_TYPES,
            "errors": errors,
            "success": success,
        },
        status_code=status_code,
    )
