import os
import uuid
import logging
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.database import get_db
from backend.models.db_models import JournalEntry, MoodScore, Nudge
from backend.routers.user import get_current_user_id
from backend.services.pdf_generator import generate_weekly_report

# Import GenSim for Topic Extraction
from gensim.parsing.preprocessing import STOPWORDS
from gensim.utils import simple_preprocess
from gensim import corpora, models

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/reports", tags=["Reports"])

# NLP Helper Function
def extract_themes(texts: list) -> list:
    """Uses GenSim LDA to find the top 3 themes hidden in the user's journal entries"""
    if not texts:
        return []
    
    # 1. Clean the text (remove punctuation, lowercase, remove "the", "and", etc.)
    processed_texts = [
        [word for word in simple_preprocess(text) if word not in STOPWORDS]
        for text in texts
    ]

    # 2. Build the dictionary and corpus for GenSim
    dictionary = corpora.Dictionary(processed_texts)
    corpus = [dictionary.doc2bow(text) for text in processed_texts]

    # 3. Train the LDA Topic Model (Looking for 3 distinct topics)
    try:
        lda_model = models.LdaModel(corpus, num_topics=3, id2word=dictionary, passes=10)
        
        themes = []
        # Extract the top 3 words for each of the 3 topics
        for idx, topic in lda_model.print_topics(num_words=3):
            # GenSim outputs weird strings like '0.045*"work" + 0.032*"stress"'. Let's clean it up:
            words = [word.split('*')[1].strip('"') for word in topic.split(' + ')]
            themes.append(", ".join(words).title())
            
        return themes
    except Exception as e:
        logger.error(f"GenSim LDA failed: {e}")
        return ["Unable to extract themes this week."]

# --- Background Task to Clean Up PDFs ---
def delete_temp_file(path: str):
    """Deletes the PDF from the server hard drive after the user downloads it."""
    try:
        if os.path.exists(path):
            os.remove(path)
    except Exception as e:
        logger.error(f"Failed to delete temp file {path}: {e}")

# --- The API Endpoint ---
@router.get("/weekly", summary="Generate and download a weekly PDF report")
async def get_weekly_report(
    background_tasks: BackgroundTasks,
    current_user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db)
):
    user_uuid = uuid.UUID(current_user_id)
    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=7)

    # 1. FETCH DATA CONCURRENTLY (Sort of!)
    # Fetch Journal Entries (for themes)
    entries_result = await db.execute(
        select(JournalEntry.raw_text).where(
            JournalEntry.user_id == user_uuid,
            JournalEntry.created_at >= start_date
        )
    )
    texts = entries_result.scalars().all()

    # Fetch Mood Scores (for trend summary)
    scores_result = await db.execute(
        select(MoodScore.fused_score).where(
            MoodScore.user_id == user_uuid,
            MoodScore.time >= start_date,
            MoodScore.fused_score.is_not(None)
        )
    )
    scores = scores_result.scalars().all()

    # Fetch Nudges (for the proactive history table)
    nudges_result = await db.execute(
        select(Nudge).where(
            Nudge.user_id == user_uuid,
            Nudge.sent_at >= start_date
        ).order_by(Nudge.sent_at.desc())
    )
    nudges = nudges_result.scalars().all()

    # 2. RUN ANALYTICS
    themes = extract_themes(list(texts))
    
    # Calculate a simple narrative summary
    if not scores:
        trend_summary = "Not enough data recorded this week to establish a trend."
    else:
        avg_score = sum(scores) / len(scores)
        if avg_score > 0.3:
            trend_summary = f"You had a highly positive week overall! Your average emotional score was {avg_score:.2f}."
        elif avg_score < -0.3:
            trend_summary = f"This week looked a bit tough. Your average emotional score was {avg_score:.2f}. Be sure to be kind to yourself."
        else:
            trend_summary = f"Your mood was fairly stable and neutral this week, with an average score of {avg_score:.2f}."

    # Format the nudge data for the PDF
    nudge_log = [{
        "date": n.sent_at.strftime("%b %d"),
        "type": n.nudge_type,
        "reason": n.trigger_reason,
        "rating": n.rating if n.rating is not None else 0
    } for n in nudges]

    # 3. GENERATE THE PDF
    # Create a unique filename so users don't overwrite each other's reports
    file_path = f"weekly_report_{user_uuid.hex}.pdf"
    
    generate_weekly_report(
        file_path=file_path,
        start_date=start_date.strftime("%B %d, %Y"),
        end_date=end_date.strftime("%B %d, %Y"),
        trend_summary=trend_summary,
        themes=themes,
        nudge_log=nudge_log
    )

    # 4. SEND TO BROWSER & CLEAN UP
    # BackgroundTasks runs AFTER the file is sent to the user, ensuring we don't clutter the server!
    background_tasks.add_task(delete_temp_file, file_path)

    return FileResponse(
        path=file_path, 
        media_type="application/pdf", 
        filename="MoodMap_Weekly_Report.pdf"
    )