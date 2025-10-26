# app/models.py
from __future__ import annotations
import enum, uuid
from sqlalchemy import (
    Column, String, Integer, Boolean, DateTime, ForeignKey,
    Enum as SAEnum, func
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import declarative_base

Base = declarative_base()

# -------- Python enums ----------
class TxType(str, enum.Enum):
    grant = "grant"
    spend = "spend"
    refund = "refund"
    purchase = "purchase"

class TxStatus(str, enum.Enum):
    pending = "pending"
    settled = "settled"
    failed = "failed"

class JobStatus(str, enum.Enum):
    queued = "queued"
    processing = "processing"
    completed = "completed"
    failed = "failed"

# -------- Tables ----------
class User(Base):
    __tablename__ = "users"
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), nullable=False, unique=True)
    password_hash = Column(String(255), nullable=False)
    credits = Column(Integer, nullable=False, default=0)
    is_admin = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, server_default=func.now())

class CreditTransaction(Base):
    __tablename__ = "credit_transactions"
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    # Храним как VARCHAR (native_enum=False), чтобы совпадало с существующей БД
    type = Column(SAEnum(TxType, name="txtype", native_enum=False), nullable=False)
    amount = Column(Integer, nullable=False)
    ref = Column(String(255))
    status = Column(SAEnum(TxStatus, name="txstatus", native_enum=False), nullable=False, server_default="settled")
    created_at = Column(DateTime, server_default=func.now())

class VideoJob(Base):
    __tablename__ = "video_jobs"
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    prompt = Column(String, nullable=False)
    style = Column(String(32))
    group_id = Column(PGUUID(as_uuid=True))
    model = Column(String(50), default="sora-2")
    size = Column(String(20), default="1280x720")
    seconds = Column(Integer, default=4)
    openai_id = Column(String(120))
    status = Column(SAEnum(JobStatus, name="jobstatus", native_enum=False), nullable=False, server_default="queued")
    cost_credits = Column(Integer, default=0)
    file_path = Column(String(512))
    file_url = Column(String(1024))
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
