from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List, Literal
from datetime import datetime
from uuid import UUID
from .models import TxType, TxStatus, JobStatus

Style = Literal["default", "80s", "bleach", "modern", "none"]
Fmt   = Literal["9:16", "16:9", "1:1"]

# ---- Auth ----
class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)

class LoginIn(BaseModel):
    email: EmailStr
    password: str

class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"

class UserOut(BaseModel):
    id: UUID
    email: EmailStr
    credits: int
    is_admin: bool
    created_at: datetime

    class Config:
        from_attributes = True

# ---- Credits ----
class CreditTxOut(BaseModel):
    id: UUID
    type: TxType
    amount: int
    ref: Optional[str]
    status: TxStatus
    created_at: datetime

    class Config:
        from_attributes = True

class GrantIn(BaseModel):
    user_id: UUID
    amount: int = Field(gt=0)

# ---- Videos ----
class VideoCreateIn(BaseModel):
    prompt: str
    seconds: Literal[4, 8, 12] = Field(..., description="Allowed: 4, 8, 12")
    format: Optional[Fmt] = Field(None, description="Will be mapped to size internally")
    style: Optional[Style] = "default"
    model: Optional[str] = "sora-2"

class VideoOut(BaseModel):
    id: UUID
    prompt: str
    model: str
    size: str
    seconds: int
    openai_id: Optional[str]
    status: JobStatus
    cost_credits: int
    file_url: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class VideoListOut(BaseModel):
    items: List[VideoOut]

class VideoBatchIn(BaseModel):
    prompt: str
    seconds: Literal[4, 8, 12] = Field(..., description="Allowed: 4, 8, 12")
    format: Optional[Fmt] = None
    model: str = "sora-2"
    styles: Optional[List[Style]] = None  # если None — сгенерим все 5

class VideoBatchOut(BaseModel):
    items: List[VideoOut]
