import logging
from concurrent.futures import ThreadPoolExecutor
from celery import shared_task

from backend.database import SyncSessionLocal
from backend.models.db_models import UserProfile
from backend.agents.distress_agent import distress_agent

logger = logging.getLogger(__name__)

def process_single_user(user_id: str):
    """
    Helper function to run the agent for one user with strict error handling.
    If one user's agent crashes, it won't break the loop for everyone else.
    """
    try:
        logger.info(f"Starting agent check for user: {user_id}")

        # This is the trigger
        # We pass the user_id into our LangGraph brain
        distress_agent.invoke({"user_id": user_id})

        logger.info(f"Successfully completed agent check for user: {user_id}")
    except Exception as e:
        logger.error(f"Agent failed for user {user_id}: {str(e)}")

@shared_task
def run_nightly_agent_check():
    """
    Runs daily. Finds all eligible users and evaluates their mood trajectory.
    Limits concurrent LLM calls to 5 at a time
    """
    logger.info("Starting nightly agent check")

    with SyncSessionLocal() as db:
        # 1. Find all users who have notifications enabled
        active_users = db.query(UserProfile.id).filter(
            UserProfile.notification_enabled == True
        ).all()

        # Extract the UUIDs into a clean list of strings
        user_ids = [str(user.id) for user in active_users]
        logger.info(f"Found {len(user_ids)} users to process.")

    if not user_ids:
        return "No users to process"
    
    # 2. Process users concurrently (Semaphore limit = 5)
    # This creates a pool of 5 workers. As soon as one finishes a user,
    # it grabs the next one, ensuring we never process more than 5 at exactly the same time
    with ThreadPoolExecutor(max_workers=5) as executor:
        executor.map(process_single_user, user_ids)

    logger.info("Nightly agent check complete!")
    return f"Processed {len(user_ids)} users"