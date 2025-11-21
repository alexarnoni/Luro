from datetime import datetime, date
from sqlalchemy import (
    Column,
    Integer,
    String,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Boolean,
    Index,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.core.database import Base


class CardStatement(Base):
    __tablename__ = "card_statements"
    __table_args__ = (
        UniqueConstraint(
            "account_id",
            "year",
            "month",
            name="uq_card_statements_account_month",
        ),
        Index("ix_card_statements_account_close", "account_id", "close_date"),
    )

    id = Column(Integer, primary_key=True)
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=False)
    year = Column(Integer, nullable=False)
    month = Column(Integer, nullable=False)
    close_date = Column(Date, nullable=False)
    due_date = Column(Date, nullable=False)
    status = Column(String(20), default="open", nullable=False)  # open, closed, paid, overdue
    amount_due = Column(Float, default=0.0, nullable=False)
    amount_paid = Column(Float, default=0.0, nullable=False)
    carry_applied = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    account = relationship("Account", backref="card_statements")
    charges = relationship("CardCharge", back_populates="statement")


class CardCharge(Base):
    __tablename__ = "card_charges"
    __table_args__ = (
        Index("ix_card_charges_account_date", "account_id", "purchase_date"),
    )

    id = Column(Integer, primary_key=True)
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=False)
    statement_id = Column(Integer, ForeignKey("card_statements.id"), nullable=True)
    purchase_date = Column(DateTime, default=datetime.utcnow, nullable=False)
    amount = Column(Float, nullable=False)
    description = Column(String, nullable=True)
    category_id = Column(Integer, ForeignKey("categories.id", ondelete="SET NULL"), nullable=True)
    installment_number = Column(Integer, default=1, nullable=False)
    installment_total = Column(Integer, default=1, nullable=False)
    merchant = Column(String, nullable=True)
    source_hash = Column(String(64), nullable=True, index=True)
    is_adjustment = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    account = relationship("Account", backref="card_charges")
    statement = relationship("CardStatement", back_populates="charges")
    category = relationship("Category", backref="card_charges")

