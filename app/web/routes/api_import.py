"""API route handling transaction file imports."""
from __future__ import annotations

import json
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.csrf import enforce_csrf_protection
from app.core.database import get_db
from app.core.rate_limit import rate_limiter
from app.core.session import get_current_user
from app.domain.imports.schemas import ImportApplyResponse, ImportMode, ImportPreviewResponse
from app.domain.imports.services import process_import
from app.domain.users.models import User

router = APIRouter()


@router.post(
    "/import",
    response_model=ImportPreviewResponse | ImportApplyResponse,
)
async def import_transactions(
    file: UploadFile = File(...),
    mode: str = Form(ImportMode.PREVIEW.value),
    account_id: Optional[int] = Form(None),
    mapping: Optional[str] = Form(None),
    overrides: Optional[str] = Form(None),
    saveRules: bool = Form(False),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _csrf: None = Depends(enforce_csrf_protection),
) -> ImportPreviewResponse | ImportApplyResponse:
    """Handle CSV/OFX imports and optionally persist transactions."""

    try:
        import_mode = ImportMode(mode)
    except ValueError as exc:  # pragma: no cover - defensive
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid import mode") from exc

    rate_limit_key = f"import:{user.id}"
    allowed = await rate_limiter.is_allowed(
        rate_limit_key,
        settings.RATE_LIMIT_MAX,
        settings.RATE_LIMIT_WINDOW_SECONDS,
    )
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many import attempts. Please try again later.",
        )

    if not file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File name is required")

    file_bytes = await file.read()

    mapping_data: Optional[dict[str, str]] = None
    if mapping:
        try:
            parsed = json.loads(mapping)
            if isinstance(parsed, dict):
                mapping_data = {str(key): str(value) for key, value in parsed.items() if value}
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid mapping payload") from exc

    overrides_data: Optional[dict[str, int]] = None
    if overrides:
        try:
            parsed_overrides = json.loads(overrides)
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid overrides payload") from exc
        else:
            if isinstance(parsed_overrides, dict):
                overrides_data = {}
                for key, value in parsed_overrides.items():
                    if not isinstance(key, str):
                        continue
                    if isinstance(value, int):
                        overrides_data[key] = value
                    elif isinstance(value, str) and value.isdigit():
                        overrides_data[key] = int(value)

    response = await process_import(
        db=db,
        user=user,
        filename=file.filename,
        file_bytes=file_bytes,
        mode=import_mode,
        mapping=mapping_data,
        provided_account_id=account_id,
        overrides=overrides_data,
        save_rules=saveRules,
    )

    return response
