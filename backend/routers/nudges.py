from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, Field
import uuid
import logging

from backend.database import get_db
from backend.models.db_models import Nudge, AgentState
from backend.routers.user import get_current_user_id
from backend.services.cache import cache_get, cache_set, cache_delete_pattern
from backend.services.encryption import decrypt

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/nudges", tags=["Nudges"])

_NUDGES_TTL = 60  # seconds


class NudgeRating(BaseModel):
    # 1 = Helpful, -1 = Not Helpful, 0 = Dismissed/Neutral
    rating: int = Field(..., ge=-1, le=1)


def update_intervention_weights(current_weights: dict, nudge_type: str, rating: int) -> dict:
    """Updates the probability weights using an Exponential Moving Average (EMA)."""
    if rating == 1:
        rating_value = 1.0
    elif rating == -1:
        rating_value = 0.0
    else:
        rating_value = 0.5

    default_weights = {
        "breathing": 0.2,
        "cbt": 0.2,
        "physical": 0.2,
        "social": 0.2,
        "referral": 0.2,
    }

    weights = current_weights if current_weights else default_weights

    old_weight = weights.get(nudge_type, 0.2)
    new_weight = (0.8 * old_weight) + (0.2 * rating_value)
    weights[nudge_type] = new_weight

    total_weight = sum(weights.values())
    if total_weight > 0:
        for key in weights:
            weights[key] = round(weights[key] / total_weight, 4)

    return weights


@router.get("", summary="List nudges for the current user (paginated)")
async def list_nudges(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=50),
    current_user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    cache_key = f"nudges:{current_user_id}:p{page}:s{page_size}"
    cached = cache_get(cache_key)
    if cached is not None:
        return cached

    user_uuid = uuid.UUID(current_user_id)
    offset = (page - 1) * page_size

    result = await db.execute(
        select(Nudge)
        .where(Nudge.user_id == user_uuid)
        .order_by(Nudge.sent_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    nudges = result.scalars().all()

    payload = {
        "nudges": [
            {
                "id": str(n.id),
                "nudge_type": n.nudge_type,
                "content": decrypt(n.content) if n.content else None,
                "rating": n.rating,
                "sent_at": n.sent_at.isoformat() if n.sent_at else None,
            }
            for n in nudges
        ],
        "page": page,
        "page_size": page_size,
    }
    cache_set(cache_key, payload, ttl_seconds=_NUDGES_TTL)
    return payload


@router.post("/{nudge_id}/rate", summary="Rate a proactive nudge")
async def rate_nudge(
    nudge_id: str,
    payload: NudgeRating,
    current_user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    user_uuid = uuid.UUID(current_user_id)
    nudge_uuid = uuid.UUID(nudge_id)

    nudge_result = await db.execute(
        select(Nudge).where(Nudge.id == nudge_uuid, Nudge.user_id == user_uuid)
    )
    nudge = nudge_result.scalar_one_or_none()

    if not nudge:
        raise HTTPException(status_code=404, detail="Nudge not found")

    nudge.rating = payload.rating

    state_result = await db.execute(
        select(AgentState).where(AgentState.user_id == user_uuid)
    )
    agent_state = state_result.scalar_one_or_none()

    if not agent_state:
        agent_state = AgentState(user_id=user_uuid, intervention_weights={})
        db.add(agent_state)

    new_weights = update_intervention_weights(
        current_weights=agent_state.intervention_weights,
        nudge_type=nudge.nudge_type,
        rating=payload.rating,
    )

    agent_state.intervention_weights = new_weights
    await db.commit()

    # Invalidate all cached pages for this user — pattern covers every page/size combo
    cache_delete_pattern(f"nudges:{current_user_id}:*")

    logger.info("Updated weights for user %s: %s", current_user_id, new_weights)
    return {"message": "Rating saved and agent weights updated", "new_weights": new_weights}
