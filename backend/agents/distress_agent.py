import os
import uuid
import random
import logging
import numpy as np
from typing import TypedDict, List, Dict
from langgraph.graph import StateGraph, END
from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import ChatPromptTemplate

from datetime import datetime, timedelta, timezone
from backend.database import SyncSessionLocal
from backend.models.db_models import MoodScore, Nudge, UserProfile, AgentState as DBAgentState
from backend.services.email import send_nudge_email, send_crisis_email
from backend.services.encryption import encrypt

# UK helplines inserted verbatim when crisis mood trajectory is detected
_UK_HELPLINES = (
    "We're concerned about you and want to make sure you have immediate support:\n\n"
    "- Samaritans: call or text 116 123 (free, 24/7, confidential)\n"
    "- Shout crisis text line: text SHOUT to 85258 (free, 24/7)\n"
    "- NHS urgent mental health: call 111, select option 2\n"
    "- CALM (men's mental health): 0800 58 58 58\n"
    "- Papyrus (under 35): 0800 068 4141\n"
    "- Emergency: call 999 if you are in immediate danger\n\n"
    "You are not alone. Please reach out."
)

logger = logging.getLogger(__name__)

# Three layers of length control for Claude's nudge:
#   1. Prompt instruction         — primary; tells Claude to stay short.
#   2. max_tokens on the LLM call — hard ceiling; Claude physically cannot exceed.
#   3. _truncate_to_sentence()    — final safety net; preserves sentence boundary.
# The token cap is set so Claude can't physically overshoot the char cap, and
# the prompt target is below the char cap so it almost never has to fire.
_MAX_NUDGE_CHARS = 480
_MAX_NUDGE_TOKENS = 130  # ~4 chars/token English ≈ 520 chars; leaves headroom
_PROMPT_TARGET_CHARS = 380  # what we ask Claude to aim for in the prompt


def _truncate_to_sentence(text: str, max_chars: int) -> str:
    """Trim to the last sentence-ending punctuation that fits in max_chars.

    Falls back to the last word boundary if no sentence end is in range, so
    we never cut mid-word. Only fires if Claude ignored both the prompt and
    the token cap — defense in depth, not the primary mechanism.
    """
    text = text.strip()
    if len(text) <= max_chars:
        return text
    window = text[:max_chars]
    last_punct = max(window.rfind("."), window.rfind("!"), window.rfind("?"))
    # Only honour the sentence boundary if it leaves at least 40% of the budget
    if last_punct >= int(max_chars * 0.4):
        return window[: last_punct + 1].rstrip()
    last_space = window.rfind(" ")
    if last_space > 0:
        return window[:last_space].rstrip(" ,;:-") + "."
    return window.rstrip()


# 1. Define the State
class AgentState(TypedDict):
    user_id: str
    mood_history: List[float]
    trajectory: Dict[str, float]
    distress_detected: bool
    is_crisis: bool   # severe enough to skip LLM and send helplines directly
    nudge_content: str
    nudge_type: str


# 2. The Math Node
def compute_trajectory(state: AgentState) -> dict:
    """Calculates the mathematical trend of the user's mood."""
    logger.info("Computing trajectory for user %s", state["user_id"])
    scores = state["mood_history"]

    if not scores or len(scores) < 3:
        return {"trajectory": {"slope": 0.0, "volatility": 0.0, "z_score": 0.0}}

    y = np.array(scores)
    x = np.arange(len(y))

    slope = np.polyfit(x, y, 1)[0]
    volatility = np.std(y)

    baseline_scores = y[:-1]
    today_score = y[-1]
    baseline_mean = np.mean(baseline_scores) if len(baseline_scores) > 0 else 0.0
    baseline_std = np.std(baseline_scores) if len(baseline_scores) > 0 else 0.0

    z_score = (today_score - baseline_mean) / baseline_std if baseline_std > 0 else 0.0

    return {
        "trajectory": {
            "slope": float(slope),
            "volatility": float(volatility),
            "z_score": float(z_score),
        }
    }


# 3. The Decision Node
def check_threshold(state: AgentState) -> dict:
    """Decides if the user's math warrants a proactive nudge."""
    traj = state["trajectory"]
    scores = state["mood_history"]

    distress = False
    is_crisis = False

    if len(scores) >= 3:
        if traj["slope"] <= -0.15:
            distress = True
        elif traj["z_score"] <= -1.5:
            distress = True
        elif all(score < -0.3 for score in scores[-3:]):
            distress = True

        # Crisis: every recent score extremely negative AND steep decline
        if all(score < -0.65 for score in scores[-3:]) and traj["slope"] <= -0.2:
            is_crisis = True
            distress = True
    elif len(scores) >= 1:
        # Fewer than 3 data points — can't compute a reliable trajectory,
        # but a single very negative score still warrants intervention.
        # These thresholds are tighter than the trajectory path to avoid
        # over-alerting on sparse data.
        latest = scores[-1]
        if latest < -0.50:
            distress = True
        if latest < -0.75:
            is_crisis = True

    logger.info("Threshold check complete. Distress: %s, Crisis: %s", distress, is_crisis)
    return {"distress_detected": distress, "is_crisis": is_crisis}


# Conditional Router
def should_generate_nudge(state: AgentState) -> str:
    if state["distress_detected"]:
        return "generate_nudge"
    return END


# 4. The Fetch Node
def fetch_history(state: AgentState) -> dict:
    """Grabs the last 7 days of mood scores from the database."""
    logger.info("Fetching history for user %s", state["user_id"])
    seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)

    with SyncSessionLocal() as db:
        scores = db.query(MoodScore).filter(
            MoodScore.user_id == uuid.UUID(state["user_id"]),
            MoodScore.time >= seven_days_ago,
            MoodScore.fused_score.isnot(None),
        ).order_by(MoodScore.time.asc()).all()

        history = [score.fused_score for score in scores]

    return {"mood_history": history}


# 5. The LLM Node
def generate_nudge(state: AgentState) -> dict:
    """Uses Claude to write a personalized nudge, or returns crisis helplines if needed."""
    logger.info("Distress detected. Determining intervention type...")

    # Crisis: skip LLM entirely, use pre-written helpline message
    if state.get("is_crisis"):
        logger.warning("Crisis flag set for user %s — returning helplines directly", state["user_id"])
        return {"nudge_content": _UK_HELPLINES, "nudge_type": "crisis"}

    with SyncSessionLocal() as db:
        user_state = db.query(DBAgentState).filter(
            DBAgentState.user_id == uuid.UUID(state["user_id"])
        ).first()

        weights_dict = (
            user_state.intervention_weights
            if user_state and user_state.intervention_weights
            else {"breathing": 0.2, "cbt": 0.2, "physical": 0.2, "social": 0.2, "referral": 0.2}
        )

    nudge_type = random.choices(
        population=list(weights_dict.keys()),
        weights=list(weights_dict.values()),
        k=1,
    )[0]

    logger.info("Agent selected intervention strategy: %s", nudge_type.upper())

    llm = ChatAnthropic(
        model="claude-haiku-4-5-20251001",
        temperature=0.7,
        max_tokens=_MAX_NUDGE_TOKENS,  # hard ceiling on what Claude can physically generate
    )

    prompt = ChatPromptTemplate.from_messages([
        (
            "system",
            "You are a compassionate mental wellness companion. "
            "Never diagnose. Always validate. Suggest, don't prescribe.\n\n"
            f"STRICT LENGTH RULE: Your entire reply MUST be {_PROMPT_TARGET_CHARS} characters or fewer "
            "and MUST end with a complete sentence (period, question mark, or exclamation point). "
            "Count characters as you compose. "
            "Write 2 to 3 short, warm sentences. One sentence must contain one actionable suggestion. "
            "If a thought will not fit inside the budget, write a SHORTER thought instead — "
            "never trail off mid-sentence, never use ellipses to imply more, never exceed the budget.",
        ),
        (
            "user",
            "Here is the user's recent emotional data:\n"
            "Mood History (last 7 days): {history}\n"
            "Trajectory Math: {trajectory}\n\n"
            f"Write a supportive nudge in {_PROMPT_TARGET_CHARS} characters or fewer, "
            "ending on a complete sentence. "
            "CRITICAL: The actionable suggestion MUST be a '{nudge_type}' exercise.",
        ),
    ])

    chain = prompt | llm
    response = chain.invoke({
        "history": state["mood_history"],
        "trajectory": state["trajectory"],
        "nudge_type": nudge_type,
    })

    # Defense in depth: if Claude somehow still overshoots, trim at a sentence boundary
    # rather than mid-word. With max_tokens + prompt rule above, this rarely fires.
    nudge_content = _truncate_to_sentence(response.content, _MAX_NUDGE_CHARS)

    return {"nudge_content": nudge_content, "nudge_type": nudge_type}


# 6. The Save Node
def send_nudge(state: AgentState) -> dict:
    """Saves the generated nudge to the database and optionally emails the user."""
    logger.info("Saving nudge to database...")

    with SyncSessionLocal() as db:
        # Guard: only send one nudge per user per 6 hours to avoid email spam
        six_hours_ago = datetime.now(timezone.utc) - timedelta(hours=6)
        recent_nudge = db.query(Nudge).filter(
            Nudge.user_id == uuid.UUID(state["user_id"]),
            Nudge.sent_at >= six_hours_ago,
        ).first()
        if recent_nudge:
            logger.info(
                "Skipping nudge for user %s — one was sent in the last 24h", state["user_id"]
            )
            return {}

        new_nudge = Nudge(
            user_id=uuid.UUID(state["user_id"]),
            nudge_type=state["nudge_type"],
            content=encrypt(state["nudge_content"]),
            trigger_reason=encrypt(f"Agent detected negative slope of {state['trajectory']['slope']:.2f}"),
        )
        db.add(new_nudge)

        user = db.query(UserProfile).filter(
            UserProfile.id == uuid.UUID(state["user_id"])
        ).first()

        # Prefer the dedicated email column (added by Codex migration); fall
        # back to username if email hasn't been populated yet.
        recipient_email = (
            user.email if user and user.email
            else user.username if user
            else None
        )
        # Allow test/staging overrides so Resend free-tier sends reach your own inbox.
        # Deliberately disabled in production to prevent routing real users' crisis
        # emails to a developer address (privacy + safety risk).
        if os.getenv("ENVIRONMENT", "production").lower() != "production":
            recipient_email = os.getenv("NUDGE_EMAIL_OVERRIDE") or recipient_email

        notifications_on = user.notification_enabled if user else True
        if recipient_email and notifications_on:
            if state.get("nudge_type") == "crisis" or state.get("is_crisis"):
                send_crisis_email(to_email=recipient_email)
            else:
                send_nudge_email(
                    to_email=recipient_email,
                    nudge_content=state["nudge_content"],
                )

        db.commit()

    return {}


# 7. Wire the Graph
workflow = StateGraph(AgentState)

workflow.add_node("fetch_history", fetch_history)
workflow.add_node("compute_trajectory", compute_trajectory)
workflow.add_node("check_threshold", check_threshold)
workflow.add_node("generate_nudge", generate_nudge)
workflow.add_node("send_nudge", send_nudge)

workflow.set_entry_point("fetch_history")
workflow.add_edge("fetch_history", "compute_trajectory")
workflow.add_edge("compute_trajectory", "check_threshold")

workflow.add_conditional_edges(
    "check_threshold",
    should_generate_nudge,
    {"generate_nudge": "generate_nudge", END: END},
)

workflow.add_edge("generate_nudge", "send_nudge")
workflow.add_edge("send_nudge", END)

distress_agent = workflow.compile()
