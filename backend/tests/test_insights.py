import pytest
import uuid
from datetime import datetime, timedelta, timezone
from backend.models.db_models import MoodScore

@pytest.mark.asyncio
async def test_get_user_insights(client, db_session, mock_user_id):
    """
    Test that the insights endpoint correctly aggregates multiple scores 
    from the same day and formats them for the frontend charts.
    """
    user_uuid = uuid.UUID(mock_user_id)
    
    # Grab today, but force the clock to exactly 12:00 PM (Noon)
    # This prevents the test from accidentally crossing midnight boundaries!
    now = datetime.now(timezone.utc)
    today_noon = now.replace(hour=12, minute=0, second=0, microsecond=0)
    
    # 1. SEED THE DATABASE
    # Score 1 at 12:00 PM
    score1 = MoodScore(user_id=user_uuid, time=today_noon, fused_score=0.8, dominant_emotion="joy")
    # Score 2 at 1:00 PM (Same day, different time -> No Unique Constraint Error!)
    score2 = MoodScore(user_id=user_uuid, time=today_noon + timedelta(hours=1), fused_score=0.4, dominant_emotion="joy")
    # Score 3 at 12:00 PM Yesterday
    score3 = MoodScore(user_id=user_uuid, time=today_noon - timedelta(days=1), fused_score=-0.5, dominant_emotion="sadness")
    
    db_session.add_all([score1, score2, score3])
    await db_session.commit()

    # 2. HIT THE ENDPOINT
    response = await client.get("/api/v1/insights")
    
    # 3. VERIFY THE AGGREGATION
    assert response.status_code == 200
    data = response.json()
    
    # Check the Trend Data (Line Chart)
    # The two scores from today (0.8 and 0.4) should be averaged to exactly 0.6!
    assert len(data["trend_data"]) == 2
    today_str = today_noon.strftime("%Y-%m-%d")
    
    today_data = next(item for item in data["trend_data"] if item["date"] == today_str)
    assert today_data["score"] == pytest.approx(0.6) 
    
    # Check the Emotion Breakdown (Pie Chart)
    # We should have 2 Joy, 1 Sadness
    assert len(data["emotion_breakdown"]) == 2
    joy_data = next(item for item in data["emotion_breakdown"] if item["name"] == "Joy")
    assert joy_data["value"] == 2