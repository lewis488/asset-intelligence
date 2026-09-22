from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, true
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base


class Authority(Base):
    __tablename__ = "authorities"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    slug = Column(String, nullable=True, unique=True)
    region = Column(String)
    created_at = Column(DateTime, server_default=func.now())

    users = relationship("User", back_populates="authority")
    assets = relationship("Asset", back_populates="authority")
    analysis_runs = relationship("AnalysisRun", back_populates="authority")


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    authority_id = Column(Integer, ForeignKey("authorities.id"), nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(String, nullable=False, default="manager")
    is_active = Column(Boolean, nullable=False, default=True, server_default=true())
    created_at = Column(DateTime, server_default=func.now())

    authority = relationship("Authority", back_populates="users")
