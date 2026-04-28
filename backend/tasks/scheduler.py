import logging
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from celery import shared_task

from backend.database import SyncSessionLocal
from backend.models.db_models import UserProfile, Nudge
from backend.agents.distress_agent import distress_agent, _UK_HELPLINES
from backend.services.email import send_crisis_email
from backend.services.encryption import encrypt

logger = logging.getLogger(__name__)

def process_single_user(user_id: str):
    """Run the distress agent for one user. Errors are caught so one crash
    doesn't abort the nightly loop for all remaining users."""
    try:
        logger.info("Starting agent check for user: %s", user_id)
        distress_agent.invoke({"user_id": user_id})
        logger.info("Completed agent check for user: %s", user_id)
    except Exception as e:
        logger.error("Agent failed for user %s: %s", user_id, e)


@shared_task
def run_immediate_agent_check(user_id: str):
    """Triggered right after analysis when a very negative fused_score is detected."""
    logger.info("Immediate distress check triggered for user %s", user_id)
    process_single_user(user_id)


@shared_task
def run_immediate_crisis_nudge(user_id: str):
    """Triggered immediately when crisis keywords are found in a journal entry."""
    logger.warning("CRISIS: immediate nudge triggered for user %s", user_id)
    try:
        user_uuid = uuid.UUID(user_id)  # convert once; used for all DB operations

        recipient_email: str | None = None

        with SyncSessionLocal() as db:
            # Respect the 24-hour cooldown so we never double-send
            yesterday = datetime.now(timezone.utc) - timedelta(hours=24)
            recent = db.query(Nudge).filter(
                Nudge.user_id == user_uuid,
                Nudge.sent_at >= yesterday,
            ).first()
            if recent:
                logger.info("Crisis nudge skipped for %s — cooldown active", user_id)
                return

            nudge = Nudge(
                user_id=user_uuid,
                nudge_type="crisis",
                content=encrypt(_UK_HELPLINES),
                trigger_reason=encrypt("Crisis keywords detected in journal text"),
            )
            db.add(nudge)

            user = db.query(UserProfile).filter(UserProfile.id == user_uuid).first()

            # Resolve email while the session is still open so we don't access
            # attributes on a detached instance outside the with-block.
            if user:
                if user.email:
                    recipient_email = user.email
                elif user.username and "@" in user.username:
                    recipient_email = user.username

            db.commit()

        if recipient_email:
            send_crisis_email(
                to_email=recipient_email,
                username=recipient_email.split("@")[0].capitalize(),
            )
        else:
            logger.warning("Crisis nudge saved for %s but no email address on record", user_id)

    except Exception as e:
        logger.error("Crisis nudge failed for user %s: %s", user_id, e)


@shared_task
def run_nightly_agent_check():
    """Runs daily. Finds all eligible users and evaluates their mood trajectory.
    Limits concurrent LLM calls to 5 at a time."""
    logger.info("Starting nightly agent check")

    with SyncSessionLocal() as db:
        active_users = db.query(UserProfile.id).filter(
            UserProfile.notification_enabled == True
        ).all()
        user_ids = [str(u.id) for u in active_users]
        logger.info("Found %d users to process.", len(user_ids))

    if not user_ids:
        return "No users to process"

    with ThreadPoolExecutor(max_workers=5) as executor:
        executor.map(process_single_user, user_ids)

    logger.info("Nightly agent check complete!")
    return f"Processed {len(user_ids)} users"
