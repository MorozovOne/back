import os
from pathlib import Path
from typing import Optional
from .config import settings

class LocalStorage:
    def __init__(self, root: str):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def save_bytes(self, job_id: str, content: bytes, ext: str = "mp4") -> str:
        path = self.root / f"{job_id}.{ext}"
        path.write_bytes(content)
        # Return a relative URL path handled by /videos/{id}/file
        return str(path)

    def get_path(self, job_id: str, ext: str = "mp4") -> Path:
        return self.root / f"{job_id}.{ext}"

try:
    import boto3
    from botocore.client import Config as BotoConfig
except Exception:
    boto3 = None

class S3Storage:
    def __init__(self):
        if not boto3:
            raise RuntimeError("boto3 not installed")
        session = boto3.session.Session(
            aws_access_key_id=settings.S3_ACCESS_KEY,
            aws_secret_access_key=settings.S3_SECRET_KEY,
            region_name=settings.S3_REGION,
        )
        self.s3 = session.client("s3", endpoint_url=settings.S3_ENDPOINT_URL, config=BotoConfig(signature_version="s3v4"))
        self.bucket = settings.S3_BUCKET

    def save_bytes(self, job_id: str, content: bytes, ext: str = "mp4") -> str:
        key = f"videos/{job_id}.{ext}"
        self.s3.put_object(Bucket=self.bucket, Key=key, Body=content, ContentType="video/mp4")
        # return presigned URL
        url = self.s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket, "Key": key},
            ExpiresIn=3600 * 24 * 7,  # 7 days
        )
        return url

def get_storage():
    if settings.STORAGE_BACKEND == "s3":
        return S3Storage()
    return LocalStorage(settings.STORAGE_LOCAL_PATH)
