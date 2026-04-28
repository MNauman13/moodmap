"""
Account-level endpoints: data export, account deletion, and consent management.

GDPR obligations covered here:
  Art. 7  — Consent must be recorded with a timestamp and freely withdrawable.
  Art. 9  — Mood/mental-health data is special-category; explicit consent required.
  Art. 15 — Right of access: GET /export returns every row we hold.
  Art. 17 — Right to erasure: DELETE / hard-deletes all user data.
  Art. 20 — Right to portability: export is machine-readable JSON.
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.database import get_db
from backend.models.db_models import (
    AgentState,
    JournalEntry,
    MoodScore,
    Nudge,
    UserProfile,
)
from backend.routers.user import AuthenticatedUser, get_current_user
from backend.services.cache import cache_delete_pattern
from backend.services.storage import r2_storage
from backend.services.encryption import decrypt

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/account", tags=["Account"])


# ─── Consent ─────────────────────────────────────────────────────────────────

class ConsentPayload(BaseModel):
    consent_given: bool


@router.post(
    "/consent",
    summary="Record or withdraw explicit consent for processing special-category data (GDPR Art. 9)",
)
async def update_consent(
    body: ConsentPayload,
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    user_uuid = uuid.UUID(current_user.user_id)
    profile = await db.get(UserProfile, user_uuid)

    if profile is None:
        # First-time sign-in: create profile with consent flag
        profile = UserProfile(
            id=user_uuid,
            email=current_user.email,
            consent_given=body.consent_given,
            consent_given_at=datetime.now(timezone.utc) if body.consent_given else None,
        )
        db.add(profile)
    else:
        profile.consent_given = body.consent_given
        profile.consent_given_at = datetime.now(timezone.utc) if body.consent_given else None

    await db.commit()

    return {
        "consent_given": body.consent_given,
        "recorded_at": profile.consent_given_at.isoformat() if profile.consent_given_at else None,
    }


@router.get(
    "/consent",
    summary="Return current consent status for the authenticated user",
)
async def get_consent(
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    user_uuid = uuid.UUID(current_user.user_id)
    profile = await db.get(UserProfile, user_uuid)
    if profile is None:
        return {"consent_given": False, "consent_given_at": None}
    return {
        "consent_given": bool(profile.consent_given),
        "consent_given_at": profile.consent_given_at.isoformat() if profile.consent_given_at else None,
    }


# ─── Export (Art. 15 / Art. 20) ──────────────────────────────────────────────

@router.get("/export", summary="Export all data MoodMap holds for the current user (GDPR Art. 15/20)")
async def export_account_data(
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Return a single JSON document containing every row tied to this user.

    Audio recordings are not embedded — each entry carries a fresh presigned
    download URL valid for ~1 hour. This satisfies Art. 20 portability in a
    machine-readable, commonly-used format.
    """
    user_uuid = uuid.UUID(current_user.user_id)

    profile = await db.get(UserProfile, user_uuid)
    entries_q = await db.execute(
        select(JournalEntry)
        .options(selectinload(JournalEntry.mood_scores))
        .where(JournalEntry.user_id == user_uuid)
        .order_by(JournalEntry.created_at.asc())
    )
    entries = entries_q.scalars().all()

    nudges_q = await db.execute(
        select(Nudge).where(Nudge.user_id == user_uuid).order_by(Nudge.sent_at.asc())
    )
    nudges = nudges_q.scalars().all()

    agent_state = await db.get(AgentState, user_uuid)

    payload: dict[str, Any] = {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "gdpr_notice": (
            "This file contains all personal data MoodMap holds for you under "
            "GDPR Art. 15 (right of access) and Art. 20 (right to portability). "
            "To request erasure, use the 'Delete Account' option in Account Settings."
        ),
        "user_id": current_user.user_id,
        "profile": _profile_to_dict(profile),
        "journal_entries": [_entry_to_dict(e) for e in entries],
        "nudges": [_nudge_to_dict(n) for n in nudges],
        "agent_state": _agent_state_to_dict(agent_state),
    }

    return JSONResponse(
        content=payload,
        headers={
            "Content-Disposition": (
                f'attachment; filename="moodmap_export_{current_user.user_id}.json"'
            ),
        },
    )


# ─── Deletion (Art. 17) ──────────────────────────────────────────────────────

@router.delete(
    "",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Permanently delete the current user's account and all associated data (GDPR Art. 17)",
)
async def delete_account(
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Hard-delete every row tied to the user plus their R2 audio objects.

    The agent_states FK now has ondelete='CASCADE' (migration c3d4e5f6a7b8),
    so the raw DELETE on user_profiles cascades to all child tables at the
    database level without needing ORM-level session management.

    The Supabase auth user is NOT deleted here — that requires the service-role
    key and should be handled by the client via supabase.auth.admin.deleteUser,
    or by the user through Supabase's hosted account portal.
    """
    user_uuid = uuid.UUID(current_user.user_id)

    # Collect audio keys before the cascade wipes the rows
    keys_q = await db.execute(
        select(JournalEntry.audio_key).where(
            JournalEntry.user_id == user_uuid,
            JournalEntry.audio_key.is_not(None),
        )
    )
    audio_keys = [k for (k,) in keys_q.all() if k]

    # Delete R2 objects first — best-effort, don't block on failures
    for key in audio_keys:
        try:
            r2_storage.delete_object(key)
        except Exception as e:
            logger.warning("R2 delete failed for %s: %s", key, e)

    # Single DELETE cascades to journal_entries, mood_scores, nudges, agent_states
    await db.execute(delete(UserProfile).where(UserProfile.id == user_uuid))
    await db.commit()

    try:
        cache_delete_pattern(f"insights:{current_user.user_id}*")
        cache_delete_pattern(f"nudges:{current_user.user_id}*")
        cache_delete_pattern(f"dashboard:{current_user.user_id}*")
    except Exception as e:
        logger.warning("Cache invalidation after account delete failed: %s", e)

    logger.info("Account deleted for user %s", current_user.user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ─── Serialization helpers ────────────────────────────────────────────────────

def _profile_to_dict(p: UserProfile | None) -> dict | None:
    if p is None:
        return None
    return {
        "id": str(p.id),
        "username": p.username,
        "email": p.email,
        "timezone": p.timezone,
        "notification_enabled": p.notification_enabled,
        "baseline_score": p.baseline_score,
        "consent_given": p.consent_given,
        "consent_given_at": p.consent_given_at.isoformat() if p.consent_given_at else None,
        "created_at": p.created_at.isoformat() if p.created_at else None,
    }


def _entry_to_dict(e: JournalEntry) -> dict:
    audio_url = None
    if e.audio_key:
        audio_url = r2_storage.generate_download_presigned_url(e.audio_key)
    return {
        "id": str(e.id),
        "raw_text": decrypt(e.raw_text),
        "audio_key": e.audio_key,
        "audio_download_url": audio_url,
        "word_count": e.word_count,
        "mood_tags": e.mood_tags or [],
        "status": str(e.status) if e.status else None,
        "created_at": e.created_at.isoformat() if e.created_at else None,
        "mood_scores": [
            {
                "time": s.time.isoformat() if s.time else None,
                "fused_score": s.fused_score,
                "dominant_emotion": s.dominant_emotion,
                "confidence": s.confidence,
                "text_joy": s.text_joy,
                "text_sadness": s.text_sadness,
                "text_anger": s.text_anger,
                "text_fear": s.text_fear,
                "text_disgust": s.text_disgust,
                "text_surprise": s.text_surprise,
                "text_neutral": s.text_neutral,
                "voice_valence": s.voice_valence,
                "voice_arousal": s.voice_arousal,
                "voice_energy": s.voice_energy,
                "analysis_version": s.analysis_version,
            }
            for s in (e.mood_scores or [])
        ],
    }


def _nudge_to_dict(n: Nudge) -> dict:
    return {
        "id": str(n.id),
        "nudge_type": n.nudge_type,
        "content": decrypt(n.content) if n.content else None,
        "trigger_reason": decrypt(n.trigger_reason) if n.trigger_reason else None,
        "rating": n.rating,
        "sent_at": n.sent_at.isoformat() if n.sent_at else None,
        "opened_at": n.opened_at.isoformat() if n.opened_at else None,
    }


def _agent_state_to_dict(s: AgentState | None) -> dict | None:
    if s is None:
        return None
    return {
        "last_checked_at": s.last_checked_at.isoformat() if s.last_checked_at else None,
        "trajectory_slope": s.trajectory_slope,
        "volatility": s.volatility,
        "distress_flag": s.distress_flag,
        "days_since_nudge": s.days_since_nudge,
        "intervention_weights": s.intervention_weights,
    }
