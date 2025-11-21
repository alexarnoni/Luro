from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, UniqueConstraint
from sqlalchemy.orm import relationship
from app.core.database import Base


class Insight(Base):
    """Insight model for financial insights and recommendations."""

    __tablename__ = "insights"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "period",
            "insight_type",
            name="uq_insights_user_period_type",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    insight_type = Column(String, nullable=False)  # spending, saving, goal, etc.
    created_at = Column(DateTime, default=datetime.utcnow)
    period = Column(String, nullable=True)
    
    # Relationships
    user = relationship("User", backref="insights")
