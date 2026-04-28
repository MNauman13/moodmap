import uuid
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timedelta, timezone
from collections import defaultdict
from pydantic import BaseModel
from typing import List

from backend.database import get_db
from backend.models.db_models import MoodScore
from backend.routers.user import get_current_user_id
from backend.services.cache import cache_get, cache_set

router = APIRouter(
    prefix="/api/v1/insights",
    tags=["insights"]
)

_INSIGHTS_TTL = 300  # 5 minutes


def _as_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


# Pydantic Schemas for Swagger UI / Frontend Typing
class TrendDataPoint(BaseModel):
    date: str
    score: float

class EmotionDataPoint(BaseModel):
    name: str
    value: int

class InsightsResponse(BaseModel):
    trend_data: List[TrendDataPoint]
    emotion_breakdown: List[EmotionDataPoint]
    calendar_data: List[TrendDataPoint]  # Recharts calendar uses the same format


# API Route
@router.get("", response_model=InsightsResponse)
async def get_user_insights(
    current_user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db)
):
    cache_key = f"insights:{current_user_id}"
    cached = cache_get(cache_key)
    if cached is not None:
        return InsightsResponse(**cached)

    user_uuid = uuid.UUID(current_user_id)
    now = datetime.now(timezone.utc)
    fifty_six_days_ago = now - timedelta(days=56)
    thirty_days_ago = now - timedelta(days=30)

    # Single query for 56 days; 30-day slice derived in Python (-1 DB roundtrip)
    stmt = select(MoodScore).where(
        MoodScore.user_id == user_uuid,
        MoodScore.time >= fifty_six_days_ago,
        MoodScore.fused_score.is_not(None),
    ).order_by(MoodScore.time.asc())

    result = await db.execute(stmt)
    all_scores = result.scalars().all()

    if not all_scores:
        return InsightsResponse(trend_data=[], emotion_breakdown=[], calendar_data=[])

    scores_30 = [s for s in all_scores if _as_utc(s.time) >= thirty_days_ago]

    # ── Aggregate 30-day data ──────────────────────────────────────
    daily_30: dict = defaultdict(list)
    emotion_counts: dict = defaultdict(int)

    for score in scores_30:
        day_str = _as_utc(score.time).strftime("%Y-%m-%d")
        daily_30[day_str].append(score.fused_score)
        if score.dominant_emotion:
            emotion_counts[score.dominant_emotion] += 1

    trend_data = sorted(
        [TrendDataPoint(date=d, score=round(sum(v) / len(v), 4)) for d, v in daily_30.items()],
        key=lambda p: p.date,
    )

    emotion_breakdown = [
        EmotionDataPoint(name=e.capitalize(), value=c)
        for e, c in sorted(emotion_counts.items(), key=lambda x: -x[1])
    ]

    # ── Aggregate 56-day data for heatmap ─────────────────────────
    daily_56: dict = defaultdict(list)
    for score in all_scores:
        day_str = _as_utc(score.time).strftime("%Y-%m-%d")
        daily_56[day_str].append(score.fused_score)

    calendar_data = sorted(
        [TrendDataPoint(date=d, score=round(sum(v) / len(v), 4)) for d, v in daily_56.items()],
        key=lambda p: p.date,
    )

    response = InsightsResponse(
        trend_data=trend_data,
        emotion_breakdown=emotion_breakdown,
        calendar_data=calendar_data,
    )

    cache_set(cache_key, response.model_dump(), ttl_seconds=_INSIGHTS_TTL)
    return response
