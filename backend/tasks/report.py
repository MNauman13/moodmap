"""
Celery task: generate the weekly PDF report asynchronously.

Flow:
  1. Router dispatches this task and returns {"task_id": "...", "status": "queued"}
  2. Worker fetches data, generates the PDF, uploads it to R2
  3. Client polls GET /api/v1/reports/status/{task_id}
  4. On completion the status endpoint returns a short-lived presigned download URL

The PDF is stored at reports/{user_id}/{task_id}.pdf in the R2 bucket.
Consider adding an R2 lifecycle rule to delete objects under reports/ after 24 hours.
"""

import os
import logging
import tempfile
import uuid
from datetime import datetime, timedelta, timezone
from collections import Counter, defaultdict

import boto3
from botocore.config import Config
from celery import shared_task

from backend.database import SyncSessionLocal
from backend.models.db_models import JournalEntry, MoodScore
from backend.services.pdf_generator import generate_weekly_report
from backend.services.encryption import decrypt
from backend.routers.reports import (
    _headline_from_avg,
    _build_summary,
    _top_emotions,
    extract_themes,
    _select_quote,
    _generate_reflection_prompts,
)

logger = logging.getLogger(__name__)

# ── R2 / S3 client ────────────────────────────────────────────────────────────
_raw_endpoint = os.getenv("CLOUDFLARE_R2_ENDPOINT", "").rstrip("/")
_s3 = boto3.client(
    "s3",
    endpoint_url=_raw_endpoint,
    aws_access_key_id=os.getenv("CLOUDFLARE_R2_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("CLOUDFLARE_R2_SECRET_ACCESS_KEY"),
    region_name="us-east-1",
    config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
)
_BUCKET = os.getenv("CLOUDFLARE_R2_BUCKET_NAME", "moodmap-audio")

# Presigned download URL valid for 5 minutes
_PRESIGNED_EXPIRY = 300


@shared_task(bind=True, queue="default")
def generate_report_task(self, user_id: str, start_date_iso: str, end_date_iso: str) -> dict:
    """
    Generates the weekly PDF for `user_id`, uploads it to R2, and returns
    {"r2_key": "<key>"} so the status endpoint can produce a presigned URL.
    """
    logger.info("[generate_report_task] Starting for user %s", user_id)

    user_uuid = uuid.UUID(user_id)
    start_date = datetime.fromisoformat(start_date_iso)
    end_date = datetime.fromisoformat(end_date_iso)

    # ── Fetch data ────────────────────────────────────────────────────────────
    with SyncSessionLocal() as db:
        entries: list[JournalEntry] = (
            db.query(JournalEntry)
            .filter(
                JournalEntry.user_id == user_uuid,
                JournalEntry.created_at >= start_date,
            )
            .order_by(JournalEntry.created_at.asc())
            .all()
        )
        scores: list[MoodScore] = (
            db.query(MoodScore)
            .filter(
                MoodScore.user_id == user_uuid,
                MoodScore.time >= start_date,
                MoodScore.fused_score.is_not(None),
            )
            .all()
        )

    # ── Compose content ───────────────────────────────────────────────────────
    avg = sum(s.fused_score for s in scores) / len(scores) if scores else None
    headline = _headline_from_avg(avg)
    summary = _build_summary(scores, entries)
    top_emotions = _top_emotions(scores, limit=4)
    themes = extract_themes([decrypt(e.raw_text) for e in entries if e.raw_text])
    quote = _select_quote(entries, scores)
    reflection_prompts = _generate_reflection_prompts(themes, top_emotions)
    days_logged = len({e.created_at.date() for e in entries})

    # ── Generate PDF ──────────────────────────────────────────────────────────
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf", prefix=f"moodmap_{user_uuid.hex}_")
    tmp_path = tmp.name
    tmp.close()

    try:
        generate_weekly_report(
            file_path=tmp_path,
            start_date=start_date.strftime("%B %d, %Y"),
            end_date=end_date.strftime("%B %d, %Y"),
            headline=headline,
            summary=summary,
            top_emotions=top_emotions,
            themes=themes,
            quote=quote,
            reflection_prompts=reflection_prompts,
            days_logged=days_logged,
        )

        # ── Upload to R2 ──────────────────────────────────────────────────────
        r2_key = f"reports/{user_id}/{self.request.id}.pdf"
        with open(tmp_path, "rb") as f:
            _s3.upload_fileobj(
                f,
                _BUCKET,
                r2_key,
                ExtraArgs={"ContentType": "application/pdf"},
            )

        logger.info("[generate_report_task] Uploaded PDF to R2 key: %s", r2_key)
        return {"r2_key": r2_key}

    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
