# app/auth.py
from passlib.hash import pbkdf2_sha256
from datetime import datetime, timedelta
from typing import Optional
from jose import jwt, JWTError
from .config import settings

def hash_password(password: str) -> str:
    return pbkdf2_sha256.hash(password)

def verify_password(password: str, password_hash: str) -> bool:
    return pbkdf2_sha256.verify(password, password_hash)

def create_access_token(subject: str, expires_minutes: int | None = None) -> str:
    to_encode = {"sub": subject, "iat": int(datetime.utcnow().timestamp())}
    expire = datetime.utcnow() + timedelta(minutes=expires_minutes or settings.JWT_EXPIRES_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.JWT_SECRET, algorithm=settings.JWT_ALG)

def decode_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALG])
    except JWTError:
        return None
