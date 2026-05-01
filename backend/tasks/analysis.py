import os
import logging
import tempfile
from datetime import datetime, timezone
import boto3
from botocore.config import Config
from celery import shared_task

from backend.database import SyncSessionLocal
from backend.models.db_models import JournalEntry, MoodScore, AnalysisStatus
from backend.services.encryption import decrypt

# ML models are optional — unavailable in CI where torch/librosa are not installed.
# The task guard below (if not _ML_AVAILABLE) returns early without crashing.
try:
    from backend.ml.text_analyser import TextEmotionAnalyzer
    from backend.ml.voice_analyser import VoiceEmotionAnalyzer
    from backend.ml.fusion import FusionModel
    _ML_AVAILABLE = True
except ImportError:
    _ML_AVAILABLE = False

logger = logging.getLogger(__name__)

_CRISIS_KEYWORDS = {
    "suicide", "suicidal", "kill myself", "end my life", "want to die",
    "don't want to live", "no point living", "better off dead", "not worth living",
    "end it all", "can't go on", "self-harm", "self harm", "hurt myself",
    "cutting myself", "overdose", "take my life", "no reason to live",
    "life isn't worth", "no way out", "give up on life",
}

_IMMEDIATE_DISTRESS_THRESHOLD = -0.75  # trigger immediate agent below this score


def _contains_crisis(text: str) -> bool:
    lower = text.lower()
    return any(kw in lower for kw in _CRISIS_KEYWORDS)


raw_endpoint = os.getenv("CLOUDFLARE_R2_ENDPOINT", "")

# Initialize ML models OUTSIDE the task so they stay cached in the worker's RAM.
# Only instantiated when the ML packages are present (i.e. real Celery workers).
if _ML_AVAILABLE:
    text_analyzer = TextEmotionAnalyzer()
    voice_analyzer = VoiceEmotionAnalyzer()
else:
    text_analyzer = None
    voice_analyzer = None

# Initialize AWS S3/Cloudflare R2 Client for downloading audio
s3_client = boto3.client(
    "s3",
    endpoint_url=raw_endpoint.rstrip("/"),
    aws_access_key_id=os.getenv("CLOUDFLARE_R2_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("CLOUDFLARE_R2_SECRET_ACCESS_KEY"),
    region_name="us-east-1",  # boto3 routing works best with this generic region
    config=Config(
        signature_version="s3v4",
        s3={'addressing_style': 'path'}  # <--- THIS IS THE MAGIC BULLET FOR CLOUDFLARE
    )
)
BUCKET_NAME = "moodmap-audio"

@shared_task(bind=True)
def analyze_entry(self, entry_id: str):
    if not _ML_AVAILABLE:
        logger.warning("[analyze_entry] ML packages not installed — skipping analysis for entry %s", entry_id)
        return {"status": "skipped", "reason": "ML unavailable"}

    logger.info(f"[analyze_entry] Starting full multimodal pipeline for entry: {entry_id}")

    with SyncSessionLocal() as db:
        entry = db.query(JournalEntry).filter(JournalEntry.id == entry_id).first()
        if not entry:
            logger.error("Entry not found in database.")
            return {"status": "error"}

        # Mark the work in flight so the SSE/status endpoints can show
        # "Analysing…" instead of the user staring at a stale "queued"
        # for the 5–15s the ML pipeline takes.
        entry.status = AnalysisStatus.PROCESSING
        db.commit()

        try:
            # Decrypt before any plaintext operation (ML analysis, crisis check)
            plain_text = decrypt(entry.raw_text)

            # --- 1. TEXT ANALYSIS ---
            logger.info("Running Text Analysis...")
            text_results = text_analyzer.analyze(plain_text)
            text_scores = text_results.get("scores", {})
            dominant_emotion = text_results.get("dominant_emotion", "neutral")
            
            # --- 2. VOICE ANALYSIS (If audio exists) ---
            voice_results = {}
            if entry.audio_key:
                logger.info(f"Audio key detected ({entry.audio_key}). Downloading from R2...")
                
                # --- WINDOWS-SAFE TEMP FILE FIX ---
                # 1. Create a named temp file but DO NOT lock it (delete=False)
                temp_audio = tempfile.NamedTemporaryFile(delete=False, suffix=".webm")
                temp_audio_path = temp_audio.name
                temp_audio.close() # 2. Immediately close Python's lock on the file!
                
                try:
                    # 3. Download the file into that unlocked path
                    with open(temp_audio_path, 'wb') as f:
                        s3_client.download_fileobj(BUCKET_NAME, entry.audio_key, f)
                        
                    logger.info("Running Voice Analysis...")
                    voice_results = voice_analyzer.analyze(temp_audio_path)
                    
                finally:
                    # 4. Manually nuke the file from your hard drive so it doesn't fill up memory
                    if os.path.exists(temp_audio_path):
                        os.remove(temp_audio_path)
            
            # --- 3. MULTIMODAL FUSION ---
            fused_score = FusionModel.fuse(text_scores, voice_results)

            # --- 4. SAVE TO TIMESCALEDB ---
            mood_score = MoodScore(
                time=datetime.now(timezone.utc),  # use actual analysis time, not creation time — avoids PK collision on concurrent entries
                user_id=entry.user_id,
                entry_id=entry.id,
                
                # Text Data
                text_joy=text_scores.get("joy", 0),
                text_love=text_scores.get("love", 0),
                text_optimism=text_scores.get("optimism", 0),
                text_sadness=text_scores.get("sadness", 0),
                text_anger=text_scores.get("anger", 0),
                text_fear=text_scores.get("fear", 0),
                text_disgust=text_scores.get("disgust", 0),
                text_surprise=text_scores.get("surprise", 0),
                text_neutral=text_scores.get("neutral", 0),
                
                # Voice Data
                voice_valence=voice_results.get("valence", None),
                voice_arousal=voice_results.get("arousal", None),
                voice_energy=voice_results.get("energy", None),
                
                # Final Calculations
                fused_score=fused_score,
                dominant_emotion=dominant_emotion,
                confidence=text_scores.get(dominant_emotion, 0),
                analysis_version="multimodal-v1"
            )
            
            db.add(mood_score)
            entry.status = AnalysisStatus.COMPLETED
            user_id = str(entry.user_id)
            db.commit()

            logger.info(f"[analyze_entry] Success! Fused Score: {fused_score} | Dominant: {dominant_emotion}")

            # Immediate intervention: check for crisis keywords or severe distress
            # Lazy imports avoid circular-import issues at module load time
            if _contains_crisis(plain_text):
                logger.warning(f"Crisis keywords detected in entry {entry_id} — triggering immediate crisis nudge")
                from backend.tasks.scheduler import run_immediate_crisis_nudge
                run_immediate_crisis_nudge.delay(user_id)
            elif fused_score < _IMMEDIATE_DISTRESS_THRESHOLD:
                logger.info(f"Severe distress score ({fused_score}) — triggering immediate agent check")
                from backend.tasks.scheduler import run_immediate_agent_check
                run_immediate_agent_check.delay(user_id)

            return {"status": "completed", "fused_score": fused_score}
            
        except Exception as e:
            logger.error(f"Pipeline crashed: {str(e)}")
            entry.status = AnalysisStatus.FAILED
            db.commit()
            return {"status": "error", "detail": str(e)}