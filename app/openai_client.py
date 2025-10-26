import httpx
import logging
from typing import Any, Dict
from .config import settings

log = logging.getLogger("openai")
BASE = "https://api.openai.com/v1"

def _headers():
    return {"Authorization": f"Bearer {settings.OPENAI_API_KEY}"}

async def create_video(final_prompt: str, model: str = "sora-2") -> Dict[str, Any]:
    # ТОЛЬКО как curl -F: multipart/form-data с двумя полями
    files = {
        "model":  (None, model),
        "prompt": (None, final_prompt),
    }
    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post(f"{BASE}/videos", headers=_headers(), files=files)
        if r.status_code >= 400:
            log.error("OpenAI /videos %s: %s", r.status_code, r.text)
            r.raise_for_status()
        return r.json()

async def get_video(openai_id: str) -> Dict[str, Any]:
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.get(f"{BASE}/videos/{openai_id}", headers=_headers())
        if r.status_code >= 400:
            log.error("OpenAI GET /videos/%s %s: %s", openai_id, r.status_code, r.text)
            r.raise_for_status()
        return r.json()

async def download_video_by_id(openai_id: str) -> bytes:
    """Качаем бинарник напрямую: /v1/videos/{id}/content"""
    async with httpx.AsyncClient(timeout=None) as client:
        r = await client.get(f"{BASE}/videos/{openai_id}/content", headers=_headers())
        if r.status_code >= 400:
            log.error("OpenAI GET /videos/%s/content %s: %s", openai_id, r.status_code, r.text)
            r.raise_for_status()
        return r.content
