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

router = APIRouter(
    prefix="/api/v1/insights",
    tags=["insights"]
)

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
    calendar_data: List[TrendDataPoint] # Recharts calendar uses the same format

# API Route
@router.get("", response_model = InsightsResponse)
async def get_user_insights(
    current_user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db)
):
    """
    Fetches the last 30 days of mood scores and formats them 
    for Recharts (Line Charts) and Calendar Heatmaps.
    """
    user_uuid = uuid.UUID(current_user_id)
    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)

    # 1. ASYNC SQLALCHEMY 2.0 QUERY
    # We query the MoodScore table directly since it holds the fused_score and time
    stmt = select(MoodScore).where(
        MoodScore.user_id == user_uuid,
        MoodScore.time >= thirty_days_ago,
        MoodScore.fused_score.is_not(None)
    ).order_by(MoodScore.time.asc())

    result = await db.execute(stmt)
    scores = result.scalars().all()

    # 2. Return empty arrays if no data exists
    if not scores:
        return InsightsResponse(
            trend_data=[],
            emotion_breakdown=[],
            calendar_data=[]
        )

    # 3. DATA AGGREGATION
    daily_scores = defaultdict(list)
    emotion_counts = defaultdict(int)

    for score in scores:
        # Extract the day string (YYYY-MM-DD)
        day_str = score.time.strftime("%Y-%m-%d")
        
        # Collect scores to average later
        daily_scores[day_str].append(score.fused_score)
        
        # Tally up the dominant emotions
        if score.dominant_emotion:
            emotion_counts[score.dominant_emotion] += 1

    # 4. FORMATTING FOR RECHARTS
    trend_data = []
    
    for day, day_scores in daily_scores.items():
        # Average the scores if the user journaled multiple times in one day
        avg_score = sum(day_scores) / len(day_scores)
        
        trend_data.append(
            TrendDataPoint(date=day, score=round(avg_score, 4))
        )

    # Convert the emotion tally dictionary into an array of objects
    emotion_breakdown = [
        EmotionDataPoint(name=emotion.capitalize(), value=count) 
        for emotion, count in emotion_counts.items()
    ]

    return InsightsResponse(
        trend_data=trend_data,
        emotion_breakdown=emotion_breakdown,
        calendar_data=trend_data # Using the same array structure for the calendar
    )