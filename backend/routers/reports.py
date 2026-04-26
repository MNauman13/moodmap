import io
import os
import uuid
import logging
import tempfile
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.database import get_db
from backend.models.db_models import JournalEntry, MoodScore, Nudge
from backend.routers.user import get_current_user_id
from backend.services.pdf_generator import generate_weekly_report
from backend.services.storage import r2_storage

from gensim.parsing.preprocessing import STOPWORDS
from gensim.utils import simple_preprocess
from gensim import corpora, models

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/reports", tags=["Reports"])

_REPORT_CACHE_TTL_HOURS = 24
_LDA_PASSES = 3  # was 10 — 70% less CPU; accuracy delta is negligible for short texts


def _report_r2_key(user_uuid: uuid.UUID) -> str:
    return f"reports/{user_uuid.hex}/weekly_report.pdf"


def _cached_report_url(user_uuid: uuid.UUID) -> str | None:
    """
    Returns a presigned download URL if a fresh cached PDF exists in R2,
    or None if the cache is missing or stale (> 24 hours old).
    """
    key = _report_r2_key(user_uuid)
    try:
        meta = r2_storage.client.head_object(
            Bucket=r2_storage.bucket_name, Key=key
        )
        last_modified: datetime = meta["LastModified"]
        age = datetime.now(timezone.utc) - last_modified
        if age < timedelta(hours=_REPORT_CACHE_TTL_HOURS):
            return r2_storage.generate_download_presigned_url(key, expires_in=3600)
    except Exception:
        pass
    return None


def extract_themes(texts: list) -> list:
    """Uses GenSim LDA to find the top 3 themes hidden in the user's journal entries."""
    if not texts:
        return []

    processed_texts = [
        [word for word in simple_preprocess(text) if word not in STOPWORDS]
        for text in texts
    ]

    dictionary = corpora.Dictionary(processed_texts)
    corpus = [dictionary.doc2bow(text) for text in processed_texts]

    try:
        lda_model = models.LdaModel(
            corpus, num_topics=3, id2word=dictionary, passes=_LDA_PASSES
        )
        themes = []
        for _idx, topic in lda_model.print_topics(num_words=3):
            words = [word.split("*")[1].strip('"') for word in topic.split(" + ")]
            themes.append(", ".join(words).title())
        return themes
    except Exception as e:
        logger.error(f"GenSim LDA failed: {e}")
        return ["Unable to extract themes this week."]


@router.get("/weekly", summary="Generate and download a weekly PDF report")
async def get_weekly_report(
    current_user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    user_uuid = uuid.UUID(current_user_id)

    # ── 1. Serve from R2 cache if still fresh ─────────────────────
    cached_url = _cached_report_url(user_uuid)
    if cached_url:
        # Redirect the browser directly to R2; zero server processing
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url=cached_url)

    # ── 2. Fetch data ──────────────────────────────────────────────
    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=7)

    entries_result = await db.execute(
        select(JournalEntry.raw_text).where(
            JournalEntry.user_id == user_uuid,
            JournalEntry.created_at >= start_date,
        )
    )
    texts = entries_result.scalars().all()

    scores_result = await db.execute(
        select(MoodScore.fused_score).where(
            MoodScore.user_id == user_uuid,
            MoodScore.time >= start_date,
            MoodScore.fused_score.is_not(None),
        )
    )
    scores = scores_result.scalars().all()

    nudges_result = await db.execute(
        select(Nudge).where(
            Nudge.user_id == user_uuid,
            Nudge.sent_at >= start_date,
        ).order_by(Nudge.sent_at.desc())
    )
    nudges = nudges_result.scalars().all()

    # ── 3. Analytics ───────────────────────────────────────────────
    themes = extract_themes(list(texts))

    if not scores:
        trend_summary = "Not enough data recorded this week to establish a trend."
    else:
        avg_score = sum(scores) / len(scores)
        if avg_score > 0.3:
            trend_summary = (
                f"You had a highly positive week overall! "
                f"Your average emotional score was {avg_score:.2f}."
            )
        elif avg_score < -0.3:
            trend_summary = (
                f"This week looked a bit tough. Your average emotional score was {avg_score:.2f}. "
                f"Be sure to be kind to yourself."
            )
        else:
            trend_summary = (
                f"Your mood was fairly stable and neutral this week, "
                f"with an average score of {avg_score:.2f}."
            )

    nudge_log = [
        {
            "date": n.sent_at.strftime("%b %d"),
            "type": n.nudge_type,
            "reason": n.trigger_reason,
            "rating": n.rating if n.rating is not None else 0,
        }
        for n in nudges
    ]

    # ── 4. Generate PDF into a temp file ──────────────────────────
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    tmp.close()
    file_path = tmp.name

    try:
        generate_weekly_report(
            file_path=file_path,
            start_date=start_date.strftime("%B %d, %Y"),
            end_date=end_date.strftime("%B %d, %Y"),
            trend_summary=trend_summary,
            themes=themes,
            nudge_log=nudge_log,
        )

        # ── 5. Upload PDF to R2 for caching ───────────────────────
        r2_key = _report_r2_key(user_uuid)
        try:
            with open(file_path, "rb") as f:
                r2_storage.client.put_object(
                    Bucket=r2_storage.bucket_name,
                    Key=r2_key,
                    Body=f,
                    ContentType="application/pdf",
                )
        except Exception as upload_err:
            logger.warning(f"Could not cache report in R2: {upload_err}")

        # ── 6. Stream PDF bytes to browser ────────────────────────
        with open(file_path, "rb") as f:
            pdf_bytes = f.read()

    finally:
        if os.path.exists(file_path):
            os.remove(file_path)

    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={
            "Content-Disposition": 'attachment; filename="MoodMap_Weekly_Report.pdf"',
        },
    )
