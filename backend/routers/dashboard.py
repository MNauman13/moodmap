"""
GET /api/v1/dashboard/summary

Returns insights + recent journal entries in a single DB round-trip,
replacing the two parallel calls the frontend previously made on page load.
"""

import uuid
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.database import get_db
from backend.models.db_models import JournalEntry, MoodScore
from backend.models.schemas import JournalEntryResponse, MoodScores
from backend.routers.insights import InsightsResponse, TrendDataPoint, EmotionDataPoint
from backend.routers.journal import _entry_to_response
from backend.routers.user import get_current_user_id
from backend.services.storage import r2_storage

router = APIRouter(prefix="/api/v1/dashboard", tags=["Dashboard"])


class DashboardSummaryResponse(BaseModel):
    insights: InsightsResponse
    recent_entries: List[JournalEntryResponse]


@router.get("/summary", response_model=DashboardSummaryResponse)
async def get_dashboard_summary(
    current_user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    user_uuid = uuid.UUID(current_user_id)
    now = datetime.now(timezone.utc)
    fifty_six_days_ago = now - timedelta(days=56)

    # Single query covering 56 days; 30-day slice derived in Python
    scores_result = await db.execute(
        select(MoodScore)
        .where(
            MoodScore.user_id == user_uuid,
            MoodScore.time >= fifty_six_days_ago,
            MoodScore.fused_score.is_not(None),
        )
        .order_by(MoodScore.time.asc())
    )
    all_scores = scores_result.scalars().all()

    thirty_days_ago = now - timedelta(days=30)
    scores_30 = [s for s in all_scores if s.time >= thirty_days_ago]

    # Recent entries (last 3) with mood scores eager-loaded
    entries_result = await db.execute(
        select(JournalEntry)
        .options(selectinload(JournalEntry.mood_scores))
        .where(JournalEntry.user_id == user_uuid)
        .order_by(JournalEntry.created_at.desc())
        .limit(3)
    )
    entries = entries_result.scalars().all()

    # Aggregate insights from in-memory data (no extra DB calls)
    daily_30: dict = defaultdict(list)
    emotion_counts: dict = defaultdict(int)
    for score in scores_30:
        day_str = score.time.strftime("%Y-%m-%d")
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

    daily_56: dict = defaultdict(list)
    for score in all_scores:
        day_str = score.time.strftime("%Y-%m-%d")
        daily_56[day_str].append(score.fused_score)

    calendar_data = sorted(
        [TrendDataPoint(date=d, score=round(sum(v) / len(v), 4)) for d, v in daily_56.items()],
        key=lambda p: p.date,
    )

    return DashboardSummaryResponse(
        insights=InsightsResponse(
            trend_data=trend_data,
            emotion_breakdown=emotion_breakdown,
            calendar_data=calendar_data,
        ),
        recent_entries=[_entry_to_response(e) for e in entries],
    )
