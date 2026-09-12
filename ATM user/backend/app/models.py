from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Float, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from backend.app.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    full_name = Column(String(150), nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    mobile = Column(String(20), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), default=datetime.utcnow)

    linked_banks = relationship("LinkedBank", back_populates="user", cascade="all, delete-orphan")

class LinkedBank(Base):
    __tablename__ = "linked_banks"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    bank_name = Column(String(100), nullable=False)
    bank_code = Column(String(20), nullable=False)
    account_masked = Column(String(30), nullable=False)
    status = Column(String(30), default="Verified", nullable=False)
    withdrawal_limit = Column(Float, nullable=False)
    currency = Column(String(10), default="₹", nullable=False)
    theme_gradient = Column(String(120), default="linear-gradient(135deg, #1e3a8a, #3b82f6)", nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), default=datetime.utcnow)

    user = relationship("User", back_populates="linked_banks")
