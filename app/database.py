# app/database.py
import asyncio
import ssl
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from .config import settings

def _connect_args_from_env():
    """
    Возвращает connect_args для asyncpg.
    disable    -> без SSL
    require    -> SSL без проверки
    verify-ca  -> проверка CA без hostname
    verify-full-> полная проверка (CA + hostname)
    """
    mode = (settings.DB_SSLMODE or "").lower().strip()
    args = {}
    if mode in ("", "disable", "disabled", "off", "false", "0"):
        # вообще без SSL
        return args
    cafile = settings.DB_SSLROOTCERT
    if mode in ("require", "required"):
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        args["ssl"] = ctx
    elif mode in ("verify-ca", "verifyca"):
        ctx = ssl.create_default_context(cafile=cafile if cafile else None)
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_REQUIRED
        args["ssl"] = ctx
    elif mode in ("verify-full", "verifyfull"):
        ctx = ssl.create_default_context(cafile=cafile if cafile else None)
        ctx.check_hostname = True
        ctx.verify_mode = ssl.CERT_REQUIRED
        args["ssl"] = ctx
    return args

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
    connect_args=_connect_args_from_env(),
)

SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

class Base(DeclarativeBase):
    pass

async def init_db():
    from . import models  # noqa
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
