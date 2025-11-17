from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String, Index

from app.core.database import Base


class LoginRequest(Base):
    """Audit and rate limiting table for magic link requests."""

    __tablename__ = "login_requests"
    __table_args__ = (
        Index("ix_login_requests_email_recent", "email", "requested_at"),
        Index("ix_login_requests_ip_recent", "ip", "requested_at"),
    )

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, nullable=False, index=True)
    ip = Column(String, nullable=True, index=True)
    requested_at = Column(DateTime, default=datetime.utcnow, index=True)


__all__ = ["LoginRequest"]
