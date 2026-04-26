import asyncio
from datetime import date, datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import selectinload
import uuid
import logging

from backend.database import get_db
from backend.routers.user import get_current_user_id as get_current_user
from backend.models.db_models import JournalEntry, MoodScore, AnalysisStatus, UserProfile
from backend.models.schemas import (
    JournalEntryCreate,
    JournalEntryCreatedResponse,
    JournalEntryResponse,
    JournalListResponse,
    MoodScores,
    PresignedUrlRequest,
    PresignedUrlResponse,
)
from backend.services.storage import r2_storage
from backend.services.rate_limiter import check_rate_limit
from backend.services.cache import cache_delete
from backend.tasks.analysis import analyze_entry

_DAILY_ENTRY_LIMIT = 20  # max journal entries per user per calendar day

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/journal", tags=["journal"])


def _entry_to_response(entry: JournalEntry) -> JournalEntryResponse:
    audio_url = None
    if entry.audio_key:
        audio_url = r2_storage.generate_download_presigned_url(entry.audio_key)

    mood_scores = None
    if entry.mood_scores:                          # fixed: was entry.mood_score
        ms = entry.mood_scores[-1]                 # most recent score
        mood_scores = MoodScores(
            text_joy=ms.text_joy,
            text_sadness=ms.text_sadness,
            text_anger=ms.text_anger,
            text_fear=ms.text_fear,
            text_disgust=ms.text_disgust,
            text_surprise=ms.text_surprise,
            text_neutral=ms.text_neutral,
            voice_valence=ms.voice_valence,
            voice_arousal=ms.voice_arousal,
            voice_energy=ms.voice_energy,
            fused_score=ms.fused_score,
            dominant_emotion=ms.dominant_emotion,
            confidence=ms.confidence,
        )

    return JournalEntryResponse(
        id=str(entry.id),
        user_id=str(entry.user_id),
        text=entry.raw_text,
        audio_key=entry.audio_key,
        audio_url=audio_url,
        word_count=entry.word_count,
        mood_tags=entry.mood_tags or [],
        status=entry.status,
        mood_scores=mood_scores,
        created_at=entry.created_at,
    )


@router.post(
    "/presigned-url",
    response_model=PresignedUrlResponse,
    summary="Get a presigned URL to upload audio directly to R2",
)
async def get_presigned_upload_url(
    body: PresignedUrlRequest,
    current_user: str = Depends(get_current_user),
):
    # 5 presigned URLs per minute per user prevents bulk-upload abuse
    check_rate_limit(f"rl:presigned:{current_user}", max_requests=5, window_seconds=60)

    result = r2_storage.generate_upload_presigned_url(
        user_id=current_user,
        file_extension=body.file_extension,
    )
    return PresignedUrlResponse(**result)


@router.post(
    "",
    response_model=JournalEntryCreatedResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit a journal entry (text + optional audio key)",
)
async def create_journal_entry(
    body: JournalEntryCreate,
    current_user: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # 10 submissions per minute per user (burst protection)
    check_rate_limit(f"rl:journal_create:{current_user}", max_requests=10, window_seconds=60)

    # Daily cap: max 20 entries per calendar day
    today_start = datetime.combine(date.today(), datetime.min.time()).replace(tzinfo=timezone.utc)
    count_today = await db.scalar(
        select(func.count()).select_from(JournalEntry).where(
            JournalEntry.user_id == uuid.UUID(current_user),
            JournalEntry.created_at >= today_start,
        )
    )
    if count_today >= _DAILY_ENTRY_LIMIT:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Daily limit of {_DAILY_ENTRY_LIMIT} journal entries reached. Try again tomorrow.",
        )

    if body.audio_key:
        if not r2_storage.object_exists(body.audio_key):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="audio_key references a file that does not exist in storage.",
            )
        if not body.audio_key.startswith(f"users/{current_user}/"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="audio_key does not belong to your account.",
            )


    stmt = insert(UserProfile).values(id=uuid.UUID(current_user)).on_conflict_do_nothing()
    await db.execute(stmt)
    await db.commit()
    entry = JournalEntry(
        user_id=uuid.UUID(current_user),
        raw_text=body.text,
        audio_key=body.audio_key,
        word_count=len(body.text.split()),
        mood_tags=body.mood_tags or [],
        status=AnalysisStatus.QUEUED,
    )
    db.add(entry)
    await db.commit()
    await db.refresh(entry)

    task = analyze_entry.delay(str(entry.id))
    logger.info(f"Queued analysis task {task.id} for entry {entry.id}")

    # Bust insights cache so the next dashboard load reflects the new entry
    cache_delete(f"insights:{current_user}")

    return JournalEntryCreatedResponse(
        entry_id=str(entry.id),
        status=AnalysisStatus.QUEUED,
        task_id=task.id,
    )


@router.get(
    "",
    response_model=JournalListResponse,
    summary="Get paginated list of journal entries for the current user",
)
async def list_journal_entries(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=50),
    current_user: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    user_id = uuid.UUID(current_user)
    offset = (page - 1) * page_size

    count_result = await db.execute(
        select(func.count()).select_from(JournalEntry).where(JournalEntry.user_id == user_id)
    )
    total = count_result.scalar_one()

    result = await db.execute(
        select(JournalEntry)
        .options(selectinload(JournalEntry.mood_scores))   # fixed: was mood_score
        .where(JournalEntry.user_id == user_id)
        .order_by(JournalEntry.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    entries = result.scalars().all()

    return JournalListResponse(
        entries=[_entry_to_response(e) for e in entries],
        total=total,
        page=page,
        page_size=page_size,
        has_more=(offset + len(entries)) < total,
    )


@router.get(
    "/{entry_id}",
    response_model=JournalEntryResponse,
    summary="Get a single journal entry with mood scores",
)
async def get_journal_entry(
    entry_id: str,
    current_user: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        entry_uuid = uuid.UUID(entry_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid entry ID format")

    result = await db.execute(
        select(JournalEntry)
        .options(selectinload(JournalEntry.mood_scores))   # fixed: was mood_score
        .where(
            JournalEntry.id == entry_uuid,
            JournalEntry.user_id == uuid.UUID(current_user),
        )
    )
    entry = result.scalar_one_or_none()
    if not entry:
        raise HTTPException(status_code=404, detail="Journal entry not found")

    return _entry_to_response(entry)


@router.get(
    "/{entry_id}/analysis-status",
    summary="Check analysis job status for an entry",
)
async def get_analysis_status(
    entry_id: str,
    current_user: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        entry_uuid = uuid.UUID(entry_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid entry ID format")

    result = await db.execute(
        select(JournalEntry.status).where(
            JournalEntry.id == entry_uuid,
            JournalEntry.user_id == uuid.UUID(current_user),
        )
    )
    row = result.first()
    if not row:
        raise HTTPException(status_code=404, detail="Entry not found")

    return {"entry_id": entry_id, "status": row[0]}


@router.get(
    "/{entry_id}/analysis-stream",
    summary="SSE stream — pushes status updates until analysis completes or fails",
)
async def stream_analysis_status(
    entry_id: str,
    current_user: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        entry_uuid = uuid.UUID(entry_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid entry ID format")

    async def event_generator():
        _TERMINAL = {"completed", "COMPLETED", "failed", "FAILED"}
        _POLL_INTERVAL = 2.0  # check DB every 2 seconds server-side

        while True:
            result = await db.execute(
                select(JournalEntry.status).where(
                    JournalEntry.id == entry_uuid,
                    JournalEntry.user_id == uuid.UUID(current_user),
                )
            )
            row = result.first()
            if not row:
                yield f"event: error\ndata: not_found\n\n"
                return

            current_status = str(row[0])
            yield f"data: {current_status}\n\n"

            if current_status in _TERMINAL:
                return

            await asyncio.sleep(_POLL_INTERVAL)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.delete(
    "/{entry_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a journal entry and its audio file",
)
async def delete_journal_entry(
    entry_id: str,
    current_user: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        entry_uuid = uuid.UUID(entry_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid entry ID format")

    result = await db.execute(
        select(JournalEntry).where(
            JournalEntry.id == entry_uuid,
            JournalEntry.user_id == uuid.UUID(current_user),
        )
    )
    entry = result.scalar_one_or_none()
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")

    if entry.audio_key:
        r2_storage.delete_object(entry.audio_key)

    await db.delete(entry)
    await db.commit()