"""
Weekly PDF report endpoint.

Pulls the last 7 days of journal entries + mood scores and renders
a humane reflection — not a metrics dashboard. Every technical signal
(z-scores, slopes, raw fused values) stays in the database; what reaches
the user is narrative, themes, a quote from their own words, and a few
reflection prompts.
"""

import os
import logging
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from typing import Optional

import boto3
from botocore.config import Config
from celery.result import AsyncResult
from fastapi import APIRouter, Depends, HTTPException

from backend.models.db_models import JournalEntry, MoodScore
from backend.routers.user import get_current_user_id
from backend.services.encryption import decrypt
from backend.celery_app import celery_app

# ── R2 client (presigned URL generation only) ─────────────────────────────────
_s3 = boto3.client(
    "s3",
    endpoint_url=os.getenv("CLOUDFLARE_R2_ENDPOINT", "").rstrip("/"),
    aws_access_key_id=os.getenv("CLOUDFLARE_R2_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("CLOUDFLARE_R2_SECRET_ACCESS_KEY"),
    region_name="us-east-1",
    config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
)
_BUCKET = os.getenv("CLOUDFLARE_R2_BUCKET_NAME", "moodmap-audio")
_PRESIGNED_EXPIRY = 300  # 5 minutes

# GenSim for theme extraction — optional (not installed in CI).
# extract_themes() returns [] when unavailable; all callers already handle that.
try:
    from gensim.parsing.preprocessing import STOPWORDS
    from gensim.utils import simple_preprocess
    from gensim import corpora, models
    _GENSIM_AVAILABLE = True
except ImportError:
    _GENSIM_AVAILABLE = False

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/reports", tags=["Reports"])


# ─── Theme extraction (LDA) ──────────────────────────────────────────────────
def extract_themes(texts: list) -> list:
    """Top 3 themes via GenSim LDA, returned as 'Word, Word, Word' strings."""
    if not texts or not _GENSIM_AVAILABLE:
        return []

    processed = [
        [w for w in simple_preprocess(t) if w not in STOPWORDS and len(w) > 2]
        for t in texts
    ]
    processed = [p for p in processed if p]
    if not processed:
        return []

    dictionary = corpora.Dictionary(processed)
    corpus = [dictionary.doc2bow(p) for p in processed]

    try:
        # Reduced passes (was 10) — produces near-identical themes much faster
        lda = models.LdaModel(corpus, num_topics=3, id2word=dictionary, passes=3)
        themes = []
        for _, topic in lda.print_topics(num_words=3):
            words = [w.split("*")[1].strip('"') for w in topic.split(" + ")]
            themes.append(", ".join(w.title() for w in words))
        return themes
    except Exception as e:
        logger.warning("LDA theme extraction failed: %s", e)
        return []


# ─── User-facing summary builders ────────────────────────────────────────────
def _headline_from_avg(avg: Optional[float]) -> str:
    """A one-line emotional shape, with no numbers visible to the user."""
    if avg is None:
        return "A quiet week"
    if avg > 0.40:
        return "A bright week"
    if avg > 0.10:
        return "A steady week"
    if avg > -0.10:
        return "A reflective week"
    if avg > -0.40:
        return "A tender week"
    return "A heavy week"


def _build_summary(
    scores: list[MoodScore],
    entries: list[JournalEntry],
) -> str:
    """A 2–4 sentence narrative paragraph. No numbers, no jargon."""
    days_logged = len({e.created_at.date() for e in entries})

    if not entries:
        return (
            "You didn't log this week, and that's okay. Sometimes the kindest "
            "thing we can do is rest. Your space here is waiting whenever you'd "
            "like to come back."
        )

    if not scores:
        return (
            f"You showed up {days_logged} {'day' if days_logged == 1 else 'days'} "
            "this week. Keeping company with your own feelings is its own kind of "
            "practice — small entries add up over time."
        )

    by_day: dict[str, list[float]] = defaultdict(list)
    for s in scores:
        by_day[s.time.strftime("%A")].append(s.fused_score)
    day_avg = {d: sum(v) / len(v) for d, v in by_day.items()}

    pieces: list[str] = []
    pieces.append(
        f"You journaled {days_logged} "
        f"{'day' if days_logged == 1 else 'days'} this week."
    )

    if len(day_avg) >= 2:
        lightest = max(day_avg, key=day_avg.get)
        heaviest = min(day_avg, key=day_avg.get)
        if lightest != heaviest:
            pieces.append(
                f"{lightest} carried the lightest weight, while {heaviest} "
                "felt the heaviest."
            )

    pieces.append(
        "Both the easy days and the harder ones are part of the same texture "
        "— noticing them is itself a kind of self-care."
    )
    return " ".join(pieces)


# Map emotion key → user-facing display name. Internal emotions are lowercase
# strings like "joy", "neutral" — surface them as something a person would say.
_EMOTION_DISPLAY = {
    "joy": "Joy",
    "love": "Love",
    "optimism": "Optimism",
    "sadness": "Sadness",
    "anger": "Frustration",   # softer than "Anger" for a wellness report
    "fear": "Anxiety",        # most users read fear as anxiety in this context
    "disgust": "Discomfort",
    "surprise": "Surprise",
    "neutral": "Calm",        # neutral = settled, not absent
}


def _top_emotions(scores: list[MoodScore], limit: int = 4) -> list[tuple[str, int]]:
    counter: Counter = Counter()
    for s in scores:
        if s.dominant_emotion:
            counter[s.dominant_emotion.lower()] += 1
    return [
        (_EMOTION_DISPLAY.get(name, name.capitalize()), count)
        for name, count in counter.most_common(limit)
    ]


def _select_quote(
    entries: list[JournalEntry],
    scores: list[MoodScore],
) -> Optional[dict]:
    """Pick the most resonant entry and format a pull-quote from it."""
    if not entries:
        return None

    # Build entry_id → fused_score map for emotional weighting
    score_by_entry = {s.entry_id: s.fused_score for s in scores if s.entry_id}

    def quote_score(e: JournalEntry) -> float:
        if not e.raw_text:
            return -1.0
        plain = decrypt(e.raw_text)
        if len(plain) < 60:
            return -1.0
        emotional_weight = abs(score_by_entry.get(e.id, 0.0))
        return min(len(plain), 400) * 0.2 + emotional_weight * 80.0

    candidates = sorted(entries, key=quote_score, reverse=True)
    if not candidates or quote_score(candidates[0]) < 0:
        return None

    chosen = candidates[0]
    text = decrypt(chosen.raw_text).strip()

    # Trim the quote at a sentence boundary so it never ends mid-thought
    if len(text) > 220:
        window = text[:220]
        last = max(window.rfind("."), window.rfind("!"), window.rfind("?"))
        text = window[: last + 1] if last > 100 else window.rstrip() + "..."

    dt = chosen.created_at
    if dt.hour < 12:
        time_of_day = "morning"
    elif dt.hour < 18:
        time_of_day = "afternoon"
    else:
        time_of_day = "evening"

    return {
        "text": text,
        "attribution": f"{dt.strftime('%A')} {time_of_day}",
    }


def _generate_reflection_prompts(
    themes: list[str],
    top_emotions: list[tuple[str, int]],
) -> list[str]:
    """Three reflection questions for next week. Claude if available, else fallback."""
    fallback = [
        "What's one moment from this week you'd like to carry forward?",
        "Where did you feel most yourself, and what made that possible?",
        "If next week could feel a degree lighter, what might help?",
    ]

    if not os.getenv("ANTHROPIC_API_KEY"):
        return fallback

    try:
        from langchain_anthropic import ChatAnthropic
        from langchain_core.prompts import ChatPromptTemplate

        llm = ChatAnthropic(
            model="claude-haiku-4-5-20251001",
            temperature=0.6,
            max_tokens=180,
        )
        prompt = ChatPromptTemplate.from_messages([
            (
                "system",
                "You are a compassionate journaling guide. Given a snapshot of "
                "someone's recent emotional themes, produce exactly 3 reflection "
                "questions for them to journal on next week. Each question should "
                "be one warm, open-ended sentence — never prescriptive, never "
                "diagnostic, never a yes/no question. Return ONLY the 3 questions "
                "as plain lines, one per line. No numbering, no bullets, no preamble.",
            ),
            (
                "user",
                "Top emotions this week: {emotions}\n"
                "Themes from journal entries: {themes}\n\n"
                "Write 3 reflection questions for next week.",
            ),
        ])

        emotions_str = ", ".join(name for name, _ in top_emotions[:3]) or "various"
        themes_str = "; ".join(themes[:3]) or "everyday life"

        response = (prompt | llm).invoke(
            {"emotions": emotions_str, "themes": themes_str}
        )
        lines = [
            line.strip().lstrip("-•0123456789. )").strip()
            for line in response.content.split("\n")
            if line.strip()
        ]
        # Keep only lines that look like real questions
        questions = [l for l in lines if l.endswith("?") and len(l) > 15]
        if len(questions) >= 2:
            return questions[:3]
    except Exception as e:
        logger.warning("Claude reflection-prompt generation failed: %s", e)

    return fallback


# ─── API endpoints ───────────────────────────────────────────────────────────

@router.post("/weekly", summary="Queue a weekly PDF report for generation", status_code=202)
async def request_weekly_report(
    current_user_id: str = Depends(get_current_user_id),
):
    """
    Dispatches PDF generation to a Celery worker and returns a task_id immediately.
    Poll GET /weekly/status/{task_id} for progress.
    """
    from backend.tasks.report import generate_report_task

    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=7)

    task = generate_report_task.delay(
        user_id=current_user_id,
        start_date_iso=start_date.isoformat(),
        end_date_iso=end_date.isoformat(),
    )
    logger.info("Report task %s queued for user %s", task.id, current_user_id)
    return {"task_id": task.id, "status": "queued"}


@router.get("/weekly/status/{task_id}", summary="Poll the status of a queued report task")
async def get_report_status(
    task_id: str,
    current_user_id: str = Depends(get_current_user_id),
):
    """
    Returns one of:
      {"status": "pending"}
      {"status": "processing"}
      {"status": "ready", "download_url": "<5-min presigned URL>", "expires_in_seconds": 300}
      {"status": "failed", "detail": "<reason>"}
    """
    result = AsyncResult(task_id, app=celery_app)
    state = result.state

    if state in ("PENDING", "RECEIVED"):
        return {"status": "pending"}
    if state == "STARTED":
        return {"status": "processing"}
    if state == "SUCCESS":
        r2_key = result.result.get("r2_key") if isinstance(result.result, dict) else None
        if not r2_key:
            raise HTTPException(status_code=500, detail="Report task succeeded but returned no file key.")
        try:
            download_url = _s3.generate_presigned_url(
                "get_object",
                Params={"Bucket": _BUCKET, "Key": r2_key},
                ExpiresIn=_PRESIGNED_EXPIRY,
            )
        except Exception as e:
            logger.error("Failed to generate presigned URL for %s: %s", r2_key, e)
            raise HTTPException(status_code=500, detail="Could not generate download link.")
        return {"status": "ready", "download_url": download_url, "expires_in_seconds": _PRESIGNED_EXPIRY}
    if state == "FAILURE":
        return {"status": "failed", "detail": str(result.result)}
    # RETRY / REVOKED / unknown
    return {"status": "pending"}
