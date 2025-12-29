from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Numeric, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base


class Account(Base):
    """Account model for user financial accounts."""
    
    __tablename__ = "accounts"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String, nullable=False)
    account_type = Column(String, nullable=False)  # checking, savings, credit, etc.
    balance = Column(Numeric(10, 2), default=0)
    currency = Column(String, default="USD")
    credit_limit = Column(Numeric(10, 2), nullable=True)
    statement_day = Column(Integer, nullable=True)  # 1-28 typically
    due_day = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", backref="accounts")
