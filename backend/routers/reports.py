"""
Weekly PDF report endpoint.

Pulls the last 7 days of journal entries + mood scores and renders
a humane reflection — not a metrics dashboard. Every technical signal
(z-scores, slopes, raw fused values) stays in the database; what reaches
the user is narrative, themes, a quote from their own words, and a few
reflection prompts.
"""

import os
import uuid
import logging
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.models.db_models import JournalEntry, MoodScore
from backend.routers.user import get_current_user_id
from backend.services.pdf_generator import generate_weekly_report
from backend.services.encryption import decrypt

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


# ─── Background cleanup ──────────────────────────────────────────────────────
def delete_temp_file(path: str) -> None:
    try:
        if os.path.exists(path):
            os.remove(path)
    except Exception as e:
        logger.warning("Failed to delete temp file %s: %s", path, e)


# ─── API endpoint ────────────────────────────────────────────────────────────
@router.get("/weekly", summary="Generate and download a weekly PDF report")
async def get_weekly_report(
    background_tasks: BackgroundTasks,
    current_user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    user_uuid = uuid.UUID(current_user_id)
    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=7)

    # Pull entries (full rows — we want raw_text for the quote)
    entries_result = await db.execute(
        select(JournalEntry)
        .where(
            JournalEntry.user_id == user_uuid,
            JournalEntry.created_at >= start_date,
        )
        .order_by(JournalEntry.created_at.asc())
    )
    entries: list[JournalEntry] = list(entries_result.scalars().all())

    # Pull mood scores (full rows — we need time, dominant_emotion, fused_score, entry_id)
    scores_result = await db.execute(
        select(MoodScore).where(
            MoodScore.user_id == user_uuid,
            MoodScore.time >= start_date,
            MoodScore.fused_score.is_not(None),
        )
    )
    scores: list[MoodScore] = list(scores_result.scalars().all())

    # ─── Compose user-facing inputs ──────────────────────────────────────────
    avg = (
        sum(s.fused_score for s in scores) / len(scores)
        if scores else None
    )
    headline = _headline_from_avg(avg)
    summary = _build_summary(scores, entries)
    top_emotions = _top_emotions(scores, limit=4)
    themes = extract_themes([decrypt(e.raw_text) for e in entries if e.raw_text])
    quote = _select_quote(entries, scores)
    reflection_prompts = _generate_reflection_prompts(themes, top_emotions)
    days_logged = len({e.created_at.date() for e in entries})

    # ─── Render & deliver ────────────────────────────────────────────────────
    # Use a temp dir + unique name so concurrent requests from the same user
    # never clobber each other's file.
    import tempfile as _tempfile
    tmp = _tempfile.NamedTemporaryFile(
        delete=False, suffix=".pdf", prefix=f"moodmap_{user_uuid.hex}_"
    )
    file_path = tmp.name
    tmp.close()  # close so generate_weekly_report can write to it on Windows

    generate_weekly_report(
        file_path=file_path,
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
    background_tasks.add_task(delete_temp_file, file_path)

    return FileResponse(
        path=file_path,
        media_type="application/pdf",
        filename="MoodMap_Weekly_Report.pdf",
    )
