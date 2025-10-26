from __future__ import annotations
import os, time, logging
from uuid import UUID
from typing import List

from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from .config import settings
from .logging_conf import setup_logging
from .database import init_db
from .deps import get_db, get_current_user, get_current_admin
from . import models, schemas
from .auth import hash_password, verify_password, create_access_token
from .openai_client import (
    create_video as oa_create_video,
    get_video as oa_get_video,
    download_video_by_id as oa_download_by_id,
)
from .storage import get_storage, LocalStorage
from .styles import compose_prompt, format_to_size

# ---- logging & app ----
setup_logging(debug=getattr(settings, "DEBUG", True))
logger = logging.getLogger("storycraft.api")
app = FastAPI(title="StoryCraft AI Backend", version="0.1.0")

@app.middleware("http")
async def log_requests(request, call_next):
    start = time.time()
    try:
        response = await call_next(request)
        logger.info("%s %s -> %s (%d ms)",
                    request.method, request.url.path,
                    getattr(response, "status_code", "?"),
                    int((time.time() - start) * 1000))
        return response
    except Exception:
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse(status_code=500, content={"detail": "Internal Server Error"})

@app.exception_handler(Exception)
async def unhandled_exc(request, exc):
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal Server Error"})

# ---- CORS ----
allow_origins = [o.strip() for o in settings.FRONTEND_ORIGINS.split(",")] if settings.FRONTEND_ORIGINS != "*" else ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def on_startup():
    os.makedirs(settings.STORAGE_LOCAL_PATH, exist_ok=True)
    await init_db()

@app.get("/health")
async def health():
    return {"ok": True}

# --------- AUTH ---------
@app.post("/auth/register", response_model=schemas.TokenOut, status_code=201)
async def register(payload: schemas.RegisterIn, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(models.User).where(models.User.email == payload.email))
    if res.scalar_one_or_none():
        raise HTTPException(400, "Email already registered")

    user = models.User(email=payload.email, password_hash=hash_password(payload.password),
                       credits=settings.WELCOME_CREDITS)
    db.add(user)
    await db.flush()

    tx = models.CreditTransaction(user_id=user.id, type=models.TxType.grant,
                                  amount=settings.WELCOME_CREDITS, ref="welcome",
                                  status=models.TxStatus.settled)
    db.add(tx)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(400, "Email already registered")
    except Exception:
        await db.rollback()
        logger.exception("Register failed for %s", payload.email)
        raise HTTPException(500, "Register failed")

    token = create_access_token(str(user.id))
    return {"access_token": token, "token_type": "bearer"}

@app.post("/auth/login", response_model=schemas.TokenOut)
async def login(payload: schemas.LoginIn, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(models.User).where(models.User.email == payload.email))
    user = res.scalar_one_or_none()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    token = create_access_token(str(user.id))
    return {"access_token": token, "token_type": "bearer"}

@app.get("/me", response_model=schemas.UserOut)
async def me(user: models.User = Depends(get_current_user)):
    return user

# --------- CREDITS ---------
@app.get("/credits/transactions", response_model=List[schemas.CreditTxOut])
async def my_transactions(user: models.User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(models.CreditTransaction)
                           .where(models.CreditTransaction.user_id == user.id)
                           .order_by(models.CreditTransaction.created_at.desc()))
    return res.scalars().all()

@app.post("/credits/grant", response_model=schemas.CreditTxOut)
async def grant_credits(payload: schemas.GrantIn, admin: models.User = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(models.User).where(models.User.id == payload.user_id))
    u = res.scalar_one_or_none()
    if not u:
        raise HTTPException(404, "User not found")
    u.credits += payload.amount
    tx = models.CreditTransaction(user_id=u.id, type=models.TxType.grant, amount=payload.amount,
                                  ref="admin_grant", status=models.TxStatus.settled)
    db.add(tx)
    await db.commit()
    await db.refresh(tx)
    return tx

# --------- VIDEOS ---------
@app.post("/videos", response_model=schemas.VideoOut, status_code=201)
async def create_video(payload: schemas.VideoCreateIn, user: models.User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if payload.seconds not in (4, 8, 12):
        raise HTTPException(400, "Allowed seconds are 4, 8, or 12")

    # размер только для метаданных/стоимости — НЕ вшиваем в prompt
    size = format_to_size(payload.format) if payload.format else "1280x720"
    final_prompt = compose_prompt(payload.style or "default", payload.prompt)

    cost = payload.seconds * settings.CREDITS_PER_SECOND
    if user.credits < cost:
        raise HTTPException(400, f"Not enough credits: need {cost}, have {user.credits}")

    uid = user.id

    # резерв
    spend_tx = models.CreditTransaction(user_id=uid, type=models.TxType.spend,
                                        amount=-cost, ref="pending", status=models.TxStatus.pending)
    db.add(spend_tx)
    user.credits -= cost

    job = models.VideoJob(user_id=uid, prompt=final_prompt, style=(payload.style or "default"),
                          model=payload.model or "sora-2", size=size, seconds=payload.seconds,
                          cost_credits=cost, status=models.JobStatus.queued)
    db.add(job)
    await db.flush()

    try:
        resp = await oa_create_video(final_prompt, model=payload.model or "sora-2")
        openai_id = resp.get("id")
        if not openai_id:
            raise RuntimeError(f"OpenAI response missing id: {resp}")
        job.openai_id = openai_id
        spend_tx.ref = str(job.id)
        await db.commit()
    except Exception as e:
        await db.rollback()
        # вернуть кредиты в новой транзакции
        async with db.begin():
            await db.execute(update(models.User).where(models.User.id == uid)
                             .values(credits=models.User.credits + cost))
            db.add(models.CreditTransaction(user_id=uid, type=models.TxType.spend,
                                            amount=-cost, ref="create_error",
                                            status=models.TxStatus.failed))
        raise HTTPException(502, detail=f"OpenAI error: {e}")

    await db.refresh(job)
    return job

@app.get("/videos", response_model=schemas.VideoListOut)
async def list_videos(user: models.User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(models.VideoJob).where(models.VideoJob.user_id == user.id)
                           .order_by(models.VideoJob.created_at.desc()))
    return {"items": res.scalars().all()}

@app.get("/videos/{job_id}", response_model=schemas.VideoOut)
async def get_video(job_id: UUID, user: models.User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(models.VideoJob)
                           .where(models.VideoJob.id == job_id, models.VideoJob.user_id == user.id))
    job = res.scalar_one_or_none()
    if not job:
        raise HTTPException(404, "Video not found")
    return job

@app.post("/videos/{job_id}/pull", response_model=schemas.VideoOut)
async def pull_video(job_id: UUID, user: models.User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(models.VideoJob)
                           .where(models.VideoJob.id == job_id, models.VideoJob.user_id == user.id))
    job = res.scalar_one_or_none()
    if not job:
        raise HTTPException(404, "Video not found")
    if not job.openai_id:
        raise HTTPException(400, "OpenAI id unknown for this job")

    try:
        info = await oa_get_video(job.openai_id)
        status_str = (info.get("status") or info.get("data", {}).get("status") or "").lower()
        if status_str in ("queued", "in_progress", "processing"):
            job.status = models.JobStatus.processing
            await db.commit()
            await db.refresh(job)
            return job
        elif status_str == "completed":
            # качаем байты из /videos/{id}/content
            content = await oa_download_by_id(job.openai_id)

            storage = get_storage()
            if isinstance(storage, LocalStorage):
                saved = storage.save_bytes(str(job.id), content, ext="mp4")
                job.file_path = saved
                job.file_url = None
            else:
                # для S3 save_bytes должен вернуть публичный/подписанный URL
                job.file_url = get_storage().save_bytes(str(job.id), content, ext="mp4")

            job.status = models.JobStatus.completed

            # закрываем spend → settled
            txq = await db.execute(select(models.CreditTransaction)
                                   .where(models.CreditTransaction.user_id == user.id,
                                          models.CreditTransaction.ref == str(job.id),
                                          models.CreditTransaction.type == models.TxType.spend,
                                          models.CreditTransaction.status == models.TxStatus.pending))
            spend = txq.scalar_one_or_none()
            if spend:
                spend.status = models.TxStatus.settled

            await db.commit()
            await db.refresh(job)
            return job
        else:
            # failed
            job.status = models.JobStatus.failed
            txq = await db.execute(select(models.CreditTransaction)
                                   .where(models.CreditTransaction.user_id == user.id,
                                          models.CreditTransaction.ref == str(job.id),
                                          models.CreditTransaction.type == models.TxType.spend,
                                          models.CreditTransaction.status == models.TxStatus.pending))
            spend = txq.scalar_one_or_none()
            if spend:
                spend.status = models.TxStatus.failed
                db.add(models.CreditTransaction(user_id=user.id, type=models.TxType.refund,
                                                amount=job.cost_credits, ref=str(job.id),
                                                status=models.TxStatus.settled))
                # вернуть кредиты
                res2 = await db.execute(select(models.User).where(models.User.id == user.id))
                u2 = res2.scalar_one()
                u2.credits += job.cost_credits
            await db.commit()
            await db.refresh(job)
            return job
    except Exception as e:
        raise HTTPException(502, f"OpenAI check/download error: {e}")

@app.post("/videos/batch", response_model=schemas.VideoBatchOut, status_code=201)
async def create_videos_batch(payload: schemas.VideoBatchIn, user: models.User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if payload.seconds not in (4, 8, 12):
        raise HTTPException(400, "Allowed seconds are 4, 8, or 12")

    size = format_to_size(payload.format) if payload.format else "1280x720"
    styles = payload.styles or ["default", "80s", "bleach", "modern", "none"]
    total_cost = len(styles) * payload.seconds * settings.CREDITS_PER_SECOND
    if user.credits < total_cost:
        raise HTTPException(400, f"Not enough credits for batch: need {total_cost}, have {user.credits}")

    uid = user.id
    created: List[models.VideoJob] = []

    for st in styles:
        cost = payload.seconds * settings.CREDITS_PER_SECOND
        spend_tx = models.CreditTransaction(user_id=uid, type=models.TxType.spend,
                                            amount=-cost, ref="pending", status=models.TxStatus.pending)
        db.add(spend_tx)
        user.credits -= cost

        final_prompt = compose_prompt(st, payload.prompt)
        job = models.VideoJob(user_id=uid, prompt=final_prompt, style=st,
                              model=payload.model or "sora-2", size=size,
                              seconds=payload.seconds, cost_credits=cost,
                              status=models.JobStatus.queued)
        db.add(job)
        await db.flush()
        try:
            resp = await oa_create_video(final_prompt, model=payload.model or "sora-2")
            openai_id = resp.get("id")
            if not openai_id:
                raise RuntimeError(f"OpenAI response missing id: {resp}")
            job.openai_id = openai_id
            spend_tx.ref = str(job.id)
            await db.commit()
            created.append(job)
        except Exception as e:
            await db.rollback()
            async with db.begin():
                await db.execute(update(models.User).where(models.User.id == uid)
                                 .values(credits=models.User.credits + cost))
                db.add(models.CreditTransaction(user_id=uid, type=models.TxType.spend,
                                                amount=-cost, ref="create_error",
                                                status=models.TxStatus.failed))
            raise HTTPException(502, detail=f"OpenAI error: {e}")

    for j in created:
        await db.refresh(j)
    return {"items": created}

@app.get("/videos/{job_id}/file")
async def download_file(job_id: UUID, user: models.User = Depends(get_current_user)):
    storage = get_storage()
    if isinstance(storage, LocalStorage):
        path = storage.get_path(str(job_id))
        if not path.exists():
            raise HTTPException(404, "File not available (yet)")
        return FileResponse(path, media_type="video/mp4", filename=f"{job_id}.mp4")
    else:
        raise HTTPException(400, "For S3, use file_url returned in job")
