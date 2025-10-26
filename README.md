# StoryCraft AI — FastAPI Backend (One‑Night MVP)

## What you get
- FastAPI + Postgres (async SQLAlchemy)
- JWT auth (register/login)
- Credits wallet & transactions
- Create Sora‑2 video jobs via OpenAI API
- Poll/pull job status + download MP4
- Local storage (S3-ready)
- CORS for your front

## Quickstart

```bash
cp .env.example .env
# edit .env: OPENAI_API_KEY, JWT_SECRET, FRONTEND_ORIGINS, etc.

docker compose up --build
```

Open: http://localhost:8000/docs

**Auth flow**
1) `POST /auth/register` {email, password} → returns JWT, gives WELCOME_CREDITS.
2) `POST /auth/login` → returns JWT.
3) Use `Authorization: Bearer <token>` for all protected endpoints.

**Jobs flow**
1) `POST /videos` with prompt/seconds/size/model → creates OpenAI job and reserves credits.
2) Front polls: `GET /videos` or `GET /videos/{id}`.
3) Trigger pull: `POST /videos/{id}/pull` (checks OpenAI, downloads MP4 if ready).
4) Download: `GET /videos/{id}/file`.

## Switch to remote Postgres
Set `DATABASE_URL` in `.env` to your remote instance:
```
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/dbname
```

## S3/MinIO (optional)
Set `STORAGE_BACKEND=s3` and fill S3_* vars. The service will upload finished videos and return a presigned URL.

## Notes
- Default `CREDITS_PER_SECOND=20` (change in `.env`).
- Transactions: spends start as `pending` and settle on successful download; on failure we refund.


## Batch generation (5 styles)
Endpoint:
```
POST /videos/batch
{
  "prompt": "Your idea",
  "seconds": 8,
  "format": "16:9",
  "styles": ["default","80s","bleach","modern","none"]  // optional; if omitted, all five
}
```
It will create 5 jobs, reserve credits per job, and return the list.

## Sora-2 API format
Requests are sent as **multipart/form-data** (`-F` style) to match your curl usage.

## Map format -> size
- 9:16 → 720x1280
- 16:9 → 1280x720
- 1:1  → 1024x1024

## Remote Postgres (SSL)
If your provider requires `sslmode=verify-full` and a CA cert:
1) Put `root.crt` into `./certs/root.crt`.
2) Set `DATABASE_URL=...&sslmode=verify-full&sslrootcert=/app/certs/root.crt` in `.env`.
3) Mount the folder by default (Dockerfile copies project, docker-compose mounts).

**Creating DB & user (psql example):**
```sql
-- Connect to default_db with admin credentials, then:
CREATE DATABASE storycraft;
GRANT ALL PRIVILEGES ON DATABASE storycraft TO gen_user;
-- Inside storycraft:
\c storycraft
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
```

## Object storage (S3/MinIO/Cloudflare R2)
Set:
```
STORAGE_BACKEND=s3
S3_BUCKET=storycraft-videos
S3_REGION=ru-1
S3_ENDPOINT_URL=https://s3.twcstorage.ru
S3_ACCESS_KEY=...
S3_SECRET_KEY=...
```
Finished MP4s will be uploaded and a **presigned URL** returned in `file_url`.

## Minimal deploy (Netherlands VM)
1) Install Docker & Docker Compose.
2) Clone project, create `.env`, set CORS `FRONTEND_ORIGINS` to your domain(s).
3) `docker compose up -d --build`
4) Put a reverse proxy (Caddy or Nginx). Example (Caddyfile):
```
api.storycraft.space {
    reverse_proxy 127.0.0.1:8000
}
```
CORS is handled in app via `FRONTEND_ORIGINS`.

## Security
- Keep your API keys and DB passwords **only** in `.env` (not in repo).
- Rotate keys if they were ever exposed.
