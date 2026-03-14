from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, Integer, String

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


class AuditLog(Base):
    """Tracks create/update/delete mutations on user data entities."""

    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_logs_user_created", "user_id", "created_at"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    action = Column(String, nullable=False)       # "create" | "update" | "delete"
    entity_type = Column(String, nullable=False)  # "transaction" | "account" | "goal" | "category" | "rule"
    entity_id = Column(Integer, nullable=True)
    detail = Column(String, nullable=True)        # JSON-serialised diff / description
    ip = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class UserSession(Base):
    """Persistent session tokens that can be individually revoked."""

    __tablename__ = "user_sessions"
    __table_args__ = (
        Index("ix_user_sessions_user_active", "user_id", "is_active"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token = Column(String, unique=True, nullable=False, index=True)  # UUID4, stored in cookie
    ip = Column(String, nullable=True)
    user_agent = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_seen_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True, nullable=False)


__all__ = ["LoginRequest", "AuditLog", "UserSession"]
