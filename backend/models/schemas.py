from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from datetime import datetime
from enum import Enum

from backend.models.db_models import AnalysisStatus


# --------------- Request Schemas ---------------

class JournalEntryCreate(BaseModel):
    text: str = Field(..., min_length=1, max_length=2000, description="Journal entry text")
    audio_key: Optional[str] = Field(
        None,
        description="Cloudflare R2 object key for uploaded audio (optional)"
    )
    mood_tags: Optional[List[str]] = Field(
        default=[],
        max_length=5,
        description="Optional pre-selected mood tags (e.g. ['anxious', 'tired'])"
    )

    @field_validator("text")
    @classmethod
    def strip_text(cls, v):
        stripped = v.strip()
        if not stripped:
            raise ValueError("Journal entry cannot be blank")
        return stripped

    @field_validator("audio_key")
    @classmethod
    def validate_audio_key(cls, v):
        if v is not None:
            # Basic safety check — key must start with "users/"
            if v is not None and not v.startswith("users/"):
                raise ValueError("Invalid audio key format")
        return v


class PresignedUrlRequest(BaseModel):
    file_extension: str = Field(
        default="webm",
        description="Audio file extension (webm, mp4, wav)"
    )

    @field_validator("file_extension")
    @classmethod
    def validate_extension(cls, v):
        allowed = {"webm", "mp4", "wav", "ogg", "m4a"}
        if v.lower() not in allowed:
            raise ValueError(f"Extension must be one of: {', '.join(allowed)}")
        return v.lower()
    

# ── Response schemas ─────────────────────────────────────────────

class MoodScores(BaseModel):
    text_joy: Optional[float] = None
    text_sadness: Optional[float] = None
    text_anger: Optional[float] = None
    text_fear: Optional[float] = None
    text_disgust: Optional[float] = None
    text_surprise: Optional[float] = None
    text_neutral: Optional[float] = None
    voice_valence: Optional[float] = None
    voice_arousal: Optional[float] = None
    voice_energy: Optional[float] = None
    fused_score: Optional[float] = None
    dominant_emotion: Optional[str] = None
    confidence: Optional[float] = None


class JournalEntryResponse(BaseModel):
    id: str
    user_id: str
    text: str
    audio_key: Optional[str]
    audio_url: Optional[str]  # Presigned download URL, generated fresh each request
    word_count: int
    mood_tags: List[str]
    status: AnalysisStatus
    mood_scores: Optional[MoodScores]
    created_at: datetime

    model_config = {"from_attributes": True}


class JournalEntryCreatedResponse(BaseModel):
    entry_id: str
    status: AnalysisStatus
    task_id: str
    message: str = "Entry saved. Analysis queued."


class PresignedUrlResponse(BaseModel):
    upload_url: str
    object_key: str
    expires_in: int


class JournalListResponse(BaseModel):
    entries: List[JournalEntryResponse]
    total: int
    page: int
    page_size: int
    has_more: bool
