"""Immutable programme assessments with append-only client review decisions."""
from sqlalchemy import Column, DateTime, ForeignKey, Integer, JSON, String, UniqueConstraint
from sqlalchemy.sql import func

from database import Base


class VaisalaProgrammePolicy(Base):
    __tablename__ = "vaisala_programme_policies"
    id = Column(Integer, primary_key=True)
    authority_id = Column(Integer, ForeignKey("authorities.id", ondelete="RESTRICT"), nullable=False, index=True)
    version = Column(String(100), nullable=False)
    policy = Column(JSON, nullable=False)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    __table_args__ = (UniqueConstraint("authority_id", "version", name="uq_vaisala_programme_policy"),)


class VaisalaProgramme(Base):
    __tablename__ = "vaisala_programmes"
    id = Column(Integer, primary_key=True)
    authority_id = Column(Integer, ForeignKey("authorities.id", ondelete="RESTRICT"), nullable=False, index=True)
    survey_id = Column(Integer, ForeignKey("vaisala_surveys.id", ondelete="RESTRICT"), nullable=False, index=True)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    idempotency_key = Column(String(120), nullable=False)
    request_fingerprint = Column(String(64), nullable=False)
    model_version = Column(String(100), nullable=False)
    policy_version = Column(String(100), nullable=False)
    merge_scale = Column(String(10), nullable=False)
    split = Column(String(20), nullable=False)
    generated_at = Column(DateTime(timezone=True), nullable=False)
    metadata_json = Column(JSON, nullable=False)
    __table_args__ = (UniqueConstraint("authority_id", "created_by", "idempotency_key", name="uq_vaisala_programme_save"),)


class VaisalaProgrammeItem(Base):
    __tablename__ = "vaisala_programme_items"
    id = Column(Integer, primary_key=True)
    programme_id = Column(Integer, ForeignKey("vaisala_programmes.id", ondelete="RESTRICT"), nullable=False, index=True)
    item_key = Column(String(200), nullable=False)
    assessment = Column(JSON, nullable=False)
    __table_args__ = (UniqueConstraint("programme_id", "item_key", name="uq_vaisala_programme_item"),)


class VaisalaProgrammeReviewEvent(Base):
    __tablename__ = "vaisala_programme_review_events"
    id = Column(Integer, primary_key=True)
    item_id = Column(Integer, ForeignKey("vaisala_programme_items.id", ondelete="RESTRICT"), nullable=False, index=True)
    sequence = Column(Integer, nullable=False)
    author_id = Column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    decision = Column(JSON, nullable=False)
    __table_args__ = (UniqueConstraint("item_id", "sequence", name="uq_vaisala_programme_review_sequence"),)
