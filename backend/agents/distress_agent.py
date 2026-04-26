import os
import random
import logging
import numpy as np
from typing import TypedDict, List, Dict
from langgraph.graph import StateGraph, END
from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import ChatPromptTemplate

from datetime import datetime, timedelta, timezone
from sqlalchemy import func
from backend.database import SyncSessionLocal
from backend.models.db_models import MoodScore, Nudge, UserProfile, AgentState as DBAgentState
from backend.services.email import send_nudge_email, send_crisis_email

# UK helplines inserted verbatim when crisis mood trajectory is detected
_UK_HELPLINES = (
    "We're concerned about you and want to make sure you have immediate support:\n\n"
    "• Samaritans — call or text 116 123 (free, 24/7, confidential)\n"
    "• Shout crisis text line — text SHOUT to 85258 (free, 24/7)\n"
    "• NHS urgent mental health — call 111, select option 2\n"
    "• CALM (men's mental health) — 0800 58 58 58\n"
    "• Papyrus (under 35) — 0800 068 4141\n"
    "• Emergency — call 999 if you are in immediate danger\n\n"
    "You are not alone. Please reach out."
)

logger = logging.getLogger(__name__)

# 1. Define the State
# This is the memory of our agent. Every node will read from this and write back to it
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
    """Calculates the mathematical trend of the user's mood"""
    logger.info(f"Computing trajectory for user {state['user_id']}")
    scores = state["mood_history"]

    # Safety check: If they just joined, we don't have enough data to calculate a trend
    if not scores or len(scores) < 3:
        return {"trajectory": {"slope": 0.0, "volatility": 0.0, "z_score": 0.0}}
    
    # Convert the list to a numpy array for advanced math
    y = np.array(scores)
    x = np.arange(len(y))

    # 1. Slope (Linear Regression) -> np.polyfit returns [slope, intercept]
    slope = np.polyfit(x, y, 1)[0]

    # 2. Volatility (Standard Deviation)
    volatility = np.std(y)

    # 3. Z-score (How far is today's score from the previous days' average?)
    baseline_scores = y[:-1]  # Everything except today
    today_score = y[-1]

    baseline_mean = np.mean(baseline_scores) if len(baseline_scores) > 0 else 0.0
    baseline_std = np.std(baseline_scores) if len(baseline_scores) > 0 else 0.0

    # Avoid division by zero if their mood has been exactly the same every day
    if baseline_std > 0:
        z_score = (today_score - baseline_mean) / baseline_std
    else:
        z_score = 0.0

    # In LangGraph, you only return the specific fields you want to update in the State
    return {
        "trajectory": {
            "slope": float(slope),
            "volatility": float(volatility),
            "z_score": float(z_score)
        }
    }


# 3. The Decision Node
def check_threshold(state: AgentState) -> dict:
    """Decides if the user's math warrants a proactive nudge"""
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

    logger.info(f"Threshold check complete. Distress: {distress}, Crisis: {is_crisis}")
    return {"distress_detected": distress, "is_crisis": is_crisis}


# The Conditional Router
def should_generate_nudge(state: AgentState) -> str:
    """This tells LangGraph where to go next based on the decision node"""
    if state["distress_detected"]:
        return "generate_nudge"
    return END  # If no distress, the agent quietly goes back to sleep


# 4. The Fetch Node
def fetch_history(state: AgentState) -> dict:
    """Grabs the last 7 days of mood scores from the database"""
    logger.info(f"Fetching history for user {state["user_id"]}")

    seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)

    # We use SyncSessionLocal because this will run inside a Celery background worker
    with SyncSessionLocal() as db:
        scores = db.query(MoodScore).filter(
            MoodScore.user_id == state['user_id'],
            MoodScore.time >= seven_days_ago,
            MoodScore.fused_score.isnot(None)
        ).order_by(MoodScore.time.asc()).all()

        # Extract just the float values for the math node
        history = [score.fused_score for score in scores]

    return {"mood_history": history}


# 5. The LLM Node - With Continual Learning
def generate_nudge(state: AgentState) -> dict:
    """Uses Claude to write a personalized nudge, or returns crisis helplines if needed."""
    logger.info("Distress detected! Determining intervention type...")

    # Crisis: skip LLM entirely, use pre-written helpline message
    if state.get("is_crisis"):
        logger.warning(f"Crisis flag set for user {state['user_id']} — returning UK helplines directly")
        return {"nudge_content": _UK_HELPLINES, "nudge_type": "crisis"}
    
    # 1. Fetch the user's custom learning weights from the database
    with SyncSessionLocal() as db:
        user_state = db.query(DBAgentState).filter(DBAgentState.user_id == state['user_id']).first()
        
        # If they have weights, use them. Otherwise, default to an equal 20% split
        weights_dict = user_state.intervention_weights if user_state and user_state.intervention_weights else {
            "breathing": 0.2, "cbt": 0.2, "physical": 0.2, "social": 0.2, "referral": 0.2
        }

    # 2. Pick the intervention type using Weighted Probability!
    # If they gave "breathing" a thumbs up yesterday, it is mathematically more likely to be picked today.
    nudge_type = random.choices(
        population=list(weights_dict.keys()),
        weights=list(weights_dict.values()),
        k=1
    )[0]
    
    logger.info(f"Agent selected intervention strategy: {nudge_type.upper()}")

    # 3. Initialize Claude
    llm = ChatAnthropic(model="claude-haiku-4-5-20251001", temperature=0.7)
    
    # 4. We update the prompt to explicitly force Claude to use the chosen strategy!
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are a compassionate mental wellness companion. "
                   "Never diagnose. Always validate. Suggest, don't prescribe. "
                   "Keep your response to exactly 3 warm, specific sentences containing one actionable suggestion."),
        ("user", "Here is the user's recent emotional data:\n"
                 "Mood History (last 7 days): {history}\n"
                 "Trajectory Math: {trajectory}\n\n"
                 "Write a supportive nudge for this user. "
                 "CRITICAL: The actionable suggestion MUST be a '{nudge_type}' exercise.") # <--- Claude will follow this rule
    ])
    
    chain = prompt | llm
    
    response = chain.invoke({
        "history": state["mood_history"],
        "trajectory": state["trajectory"],
        "nudge_type": nudge_type
    })
    
    return {
        "nudge_content": response.content,
        "nudge_type": nudge_type
    }


# 6. The Save Node
def send_nudge(state: AgentState) -> dict:
    """Saves the generated nudge to the database"""
    logger.info("Saving nudge to database...")

    with SyncSessionLocal() as db:
        # Guard: only send one nudge per user per 24 hours to avoid email spam
        yesterday = datetime.now(timezone.utc) - timedelta(hours=24)
        recent_nudge = db.query(Nudge).filter(
            Nudge.user_id == state['user_id'],
            Nudge.sent_at >= yesterday,
        ).first()
        if recent_nudge:
            logger.info(f"Skipping nudge for user {state['user_id']} — one was sent in the last 24h")
            return {}

        # 1. Save to database
        new_nudge = Nudge(
            user_id=state['user_id'],
            nudge_type=state['nudge_type'],
            content=state['nudge_content'],
            trigger_reason=f"Agent detected negative slope of {state['trajectory']['slope']:.2f}",
        )
        db.add(new_nudge)

        # 2. Get the user's profile to find their name/email
        user = db.query(UserProfile).filter(UserProfile.id == state['user_id']).first()

        if user and user.username:
            name = user.username.split('@')[0].capitalize()
            if state.get("nudge_type") == "crisis" or state.get("is_crisis"):
                send_crisis_email(to_email=user.username, username=name)
            else:
                send_nudge_email(
                    to_email=user.username,
                    username=name,
                    nudge_content=state['nudge_content'],
                )

        db.commit()

    return {}  # No state updates needed here


# 7. Wiring the Graph Together
workflow = StateGraph(AgentState)

# Add all the nodes we built
workflow.add_node("fetch_history", fetch_history)
workflow.add_node("compute_trajectory", compute_trajectory)
workflow.add_node("check_threshold", check_threshold)
workflow.add_node("generate_nudge", generate_nudge)
workflow.add_node("send_nudge", send_nudge)

# Define the execution flow (The Edges)
workflow.set_entry_point("fetch_history")
workflow.add_edge("fetch_history", "compute_trajectory")
workflow.add_edge("compute_trajectory", "check_threshold")

# The Conditional Router
workflow.add_conditional_edges(
    "check_threshold", 
    should_generate_nudge, 
    {
        "generate_nudge": "generate_nudge",
        END: END # If should_generate_nudge returns END, the graph stops here.
    }
)

workflow.add_edge("generate_nudge", "send_nudge")
workflow.add_edge("send_nudge", END)

# Compile it into a runnable application
distress_agent = workflow.compile()