from __future__ import annotations

import gettext
import os
from typing import Callable
import contextvars

from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request

# Context variable to hold the active gettext function for the request
_translator_ctx: contextvars.ContextVar[Callable[[str], str] | None] = contextvars.ContextVar(
    "_translator_ctx", default=None
)

# Directory where locale files live (project root "locale")
LOCALES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "locale")


def _load_translator_for(locale: str) -> Callable[[str], str]:
    """Load a gettext translator for the given locale. Falls back to identity.

    Returns a callable gettext-like function.
    """
    try:
        # Expected domain/file: locale/<lang>/LC_MESSAGES/messages.mo
        trans = gettext.translation("messages", localedir=LOCALES_DIR, languages=[locale], fallback=True)
        return trans.gettext
    except Exception:
        # Fallback to identity
        return lambda s: s


def set_locale_for_request(locale: str | None) -> None:
    """Set the translator in the contextvar for the active request."""
    if not locale:
        _translator_ctx.set(lambda s: s)
        return

    # Normalize common short codes
    if locale.lower().startswith("pt"):
        code = "pt_BR"
    else:
        code = "en"

    _translator_ctx.set(_load_translator_for(code))


def gettext_proxy(msg: str) -> str:
    """Proxy function that resolves the current request translator and translates msg."""
    t = _translator_ctx.get()
    if not t:
        return msg
    try:
        return t(msg)
    except Exception:
        return msg


class I18nMiddleware(BaseHTTPMiddleware):
    """Middleware that sets the appropriate gettext translator for each request.

    It checks the `lang` cookie first, then the Accept-Language header, and
    falls back to English.
    """

    async def dispatch(self, request: Request, call_next):
        # Determine desired locale: cookie -> accept-language header -> default
        locale = None
        try:
            locale = request.cookies.get("lang")
        except Exception:
            locale = None

        if not locale:
            al = request.headers.get("accept-language", "")
            if al:
                # take the first language token
                locale = al.split(",")[0].strip()

        # Set translator for this request (contextvar)
        set_locale_for_request(locale)

        # Continue processing
        response = await call_next(request)
        return response


__all__ = ["I18nMiddleware", "gettext_proxy", "set_locale_for_request"]
