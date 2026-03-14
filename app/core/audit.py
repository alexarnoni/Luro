"""Utility for recording user-action audit log entries."""
from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.security.models import AuditLog

logger = logging.getLogger(__name__)


async def log_action(
    db: AsyncSession,
    *,
    user_id: int,
    action: str,
    entity_type: str,
    entity_id: int | None = None,
    detail: dict[str, Any] | str | None = None,
    ip: str | None = None,
) -> None:
    """Append an AuditLog record to the current database session.

    The record is added with ``db.add()`` but *not* committed — the caller is
    responsible for committing together with the main operation so both succeed
    or fail atomically.

    Args:
        db: The active async SQLAlchemy session.
        user_id: ID of the user performing the action.
        action: One of ``"create"``, ``"update"``, or ``"delete"``.
        entity_type: Domain noun, e.g. ``"transaction"``, ``"account"``, ``"goal"``.
        entity_id: Primary key of the affected entity (optional).
        detail: Optional dict or string describing what changed.
        ip: Client IP address (optional).
    """
    detail_str: str | None = None
    if isinstance(detail, dict):
        try:
            detail_str = json.dumps(detail, default=str, ensure_ascii=False)
        except Exception:  # noqa: BLE001
            detail_str = str(detail)
    elif detail is not None:
        detail_str = str(detail)

    entry = AuditLog(
        user_id=user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        detail=detail_str,
        ip=ip,
    )
    db.add(entry)
