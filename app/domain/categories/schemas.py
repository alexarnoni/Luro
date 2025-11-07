"""Pydantic schemas for category operations."""
from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict


class CategoryBase(BaseModel):
    """Shared attributes for category payloads."""

    name: str | None = None
    type: Literal["income", "expense"] | None = None
    color: Optional[str] = None

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class CategoryCreate(CategoryBase):
    """Schema for creating a category."""

    name: str
    type: Literal["income", "expense"]


class CategoryUpdate(CategoryBase):
    """Schema for updating a category."""

    pass


class CategoryOut(BaseModel):
    """Schema for returning category data."""

    id: int
    name: str
    type: Literal["income", "expense"]
    color: Optional[str]
    created_at: Optional[datetime]
    updated_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)


class CategoryReassignRequest(BaseModel):
    """Schema for reassigning transactions from one category to another."""

    new_category_id: int

    model_config = ConfigDict(extra="forbid")
