import logging
from celery import shared_task
from backend.database import SyncSessionLocal
from backend.models.db_models import JournalEntry, MoodScore
from backend.ml.text_analyzer import TextEmotionAnalyzer

logger = logging.getLogger(__name__)

# IMPORTANT: We initialize the analyzer OUTSIDE the task function.
# This ensures the Celery worker downloads/loads the heavy model only ONCE 
# when it boots up, instead of re-loading it for every single journal entry.
text_analyzer = TextEmotionAnalyzer()

@shared_task(bind=True)
def analyze_entry(self, entry_id: str):
    logger.info(f"[analyze_entry] Starting real AI analysis for entry_id = {entry_id}")
    
    with SyncSessionLocal() as db:
        # 1. Fetch the entry from the database
        entry = db.query(JournalEntry).filter(JournalEntry.id == entry_id).first()
        if not entry:
            logger.error(f"Entry {entry_id} not found.")
            return {"status": "error", "detail": "Entry not found"}

        try:
            # 2. Run the text through your RoBERTa model!
            logger.info("Running NLP text analysis...")
            analysis_result = text_analyzer.analyze(entry.raw_text)
            
            scores = analysis_result["scores"]
            dominant = analysis_result["dominant_emotion"]
            
            # 3. Calculate a basic "Fused Score" (-1.0 to 1.0)
            # For now, we compare positive vs negative emotions.
            # (We will add the audio valence into this math on Day 5).
            positive_vibe = scores.get("joy", 0) + scores.get("surprise", 0)
            negative_vibe = scores.get("sadness", 0) + scores.get("anger", 0) + scores.get("fear", 0) + scores.get("disgust", 0)
            fused_score = round(positive_vibe - negative_vibe, 4)

            # 4. Save the actual ML results to the database
            mood_score = MoodScore(
                time=entry.created_at,
                user_id=entry.user_id,
                entry_id=entry.id,
                text_joy=scores.get("joy", 0),
                text_sadness=scores.get("sadness", 0),
                text_anger=scores.get("anger", 0),
                text_fear=scores.get("fear", 0),
                text_disgust=scores.get("disgust", 0),
                text_surprise=scores.get("surprise", 0),
                text_neutral=scores.get("neutral", 0),
                fused_score=fused_score,
                dominant_emotion=dominant,
                confidence=scores.get(dominant, 0),
                analysis_version="roberta-v1"
            )
            
            db.add(mood_score)
            
            # Mark the entry as successfully analyzed
            entry.status = "COMPLETED"
            db.commit()
            
            logger.info(f"[analyze_entry] Success! Fused Score: {fused_score} | Dominant: {dominant}")
            
            return {
                "status": "completed",
                "entry_id": str(entry_id),
                "fused_score": fused_score,
                "dominant_emotion": dominant
            }
            
        except Exception as e:
            logger.error(f"Analysis failed for {entry_id}: {str(e)}")
            entry.status = "FAILED"
            db.commit()
            return {"status": "error", "detail": str(e)}