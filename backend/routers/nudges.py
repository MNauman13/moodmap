from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, Field
import uuid
import logging

from backend.database import get_db
from backend.models.db_models import Nudge, AgentState
from backend.routers.user import get_current_user_id

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/nudges", tags=["Nudges"])

# Pydantic Schema
class NudgeRating(BaseModel):
    # 1 = Helpful, -1 = Not Helpful, 0 = Dismissed/Neutral
    rating: int = Field(..., ge=-1, le=1)

# The Math Helper Function
def update_intervention_weights(current_weights: dict, nudge_type: str, rating: int) -> dict:
    """
    Updates the probability weights using an Exponential Moving Average (EMA)
    """
    # 1. Convert the -1, 0, 1 rating into a mathematical percentage
    if rating == 1:
        rating_value = 1.0  # 100% Helpful
    elif rating == -1:
        rating_value = 0.0   # 0% Helpful
    else:
        rating_value = 0.5  # Neutral

    # 2. Define the default baseline if the user has no weights yet
    default_weights = {
        "breathing": 0.2,
        "cbt": 0.2,
        "physical": 0.2,
        "social": 0.2,
        "referral": 0.2
    }

    # If the user has no weights, start them at the default
    weights = current_weights if current_weights else default_weights

    # 3. Apply the Exponential Moving Average
    # We keep 80% of their historical preference, and add 20% of their new rating
    old_weight = weights.get(nudge_type, 0.2)
    new_weight = (0.8 * old_weight) + (0.2 * rating_value)

    weights[nudge_type] = new_weight

    # 4. Normalise the weights so they always sum up to exactly 1.0
    total_weight = sum(weights.values())
    if total_weight > 0:
        for key in weights:
            weights[key] = round(weights[key] / total_weight, 4)

    return weights


# The API Endpoint
@router.post("/{nudge_id}/rate", summary="Rate a proactive nudge")
async def rate_nudge(
    nudge_id: str,
    payload: NudgeRating,
    current_user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db)
):
    user_uuid = uuid.UUID(current_user_id)
    nudge_uuid = uuid.UUID(nudge_id)

    # 1. Find the specific nudge the user is rating
    nudge_result = await db.execute(
        select(Nudge).where(Nudge.id == nudge_uuid, Nudge.user_id == user_uuid)
    )
    nudge = nudge_result.scalar_one_or_none()

    if not nudge:
        raise HTTPException(status_code=404, detail="Nudge not found")
    
    # 2. Update the rating on the Nudge table
    nudge.rating = payload.rating

    # 3. Fetch the user's AgentState (where the learning weights are stored)
    state_result = await db.execute(
        select(AgentState).where(AgentState.user_id == user_uuid)
    )
    agent_state = state_result.scalar_one_or_none()

    # If the user doesn't have an agent state yet, create one
    if not agent_state:
        agent_state = AgentState(user_id=user_uuid, intervention_weights={})
        db.add(agent_state)

    # 4. Run the math to update their personal weights
    new_weights = update_intervention_weights(
        current_weights = agent_state.intervention_weights,
        nudge_type = nudge.nudge_type,
        rating = payload.rating
    )

    # Save the new brain weights to the database
    agent_state.intervention_weights = new_weights
    await db.commit()

    logger.info(f"Updated weights for user {current_user_id}: {new_weights}")
    return {"message": "Rating saved and agent weights updated", "new_weights": new_weights}