"""Pydantic schemas for transaction import workflows."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class ImportMode(str, Enum):
    """Possible modes supported by the import endpoint."""

    PREVIEW = "preview"
    APPLY = "apply"


class ImportSummary(BaseModel):
    """Aggregate information about a parsed import file."""

    total_rows: int
    parsed_rows: int
    skipped_rows: int
    currency_guess: Optional[str] = None


class ImportPreviewItem(BaseModel):
    """A normalized transaction preview entry."""

    index: int
    date: Optional[datetime] = None
    description: str
    amount: float
    transaction_type: str
    account_id: Optional[int] = None
    account_name: Optional[str] = None
    category_id: Optional[int] = None
    category_name: Optional[str] = None
    suggested_category_id: Optional[int] = None
    matched_rule_id: Optional[int] = None
    source_hash: str
    duplicate: bool = False
    warnings: List[str] = Field(default_factory=list)


class ImportPreviewResponse(BaseModel):
    """Response body returned for preview requests."""

    summary: ImportSummary
    columns: List[str]
    items: List[ImportPreviewItem]


class ImportApplyResponse(BaseModel):
    """Response body returned when transactions are persisted."""

    inserted: int
    duplicates: int
    failed: int
    created_rules: int
    updated_rules: int
