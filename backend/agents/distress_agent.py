import os
import logging
import numpy as np
from typing import TypedDict, List, Dict
from langgraph.graph import StateGraph, END
from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import ChatPromptTemplate

from datetime import datetime, timedelta, timezone
from backend.database import SyncSessionLocal
from backend.models.db_models import MoodScore, Nudge, UserProfile
from backend.services.email import send_nudge_email

logger = logging.getLogger(__name__)

# 1. Define the State
# This is the memory of our agent. Every node will read from this and write back to it
class AgentState(TypedDict):
    user_id: str
    mood_history: List[float]  # The last 7 days of fused_scores
    trajectory: Dict[str, float]  # The math: slope, volatility, z_score
    distress_detected: bool  # Yes or No flag
    nudge_content: str  # The actual message written by Claude
    nudge_type: str  # e.g. 'cbt', 'breathing', 'social'


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

    if len(scores) >= 3:
        # Rule 1: A rapid downward spiral (Slope is very negative)
        if traj["slope"] <= -0.15:
            distress = True

        # Rule 2: An anomaly (Today is significantly worse than their baseline)
        elif traj["z_score"] <= -1.5:
            distress = True

        # Rule 3: Chronic low mood (The last 3 days have all been deeply negative)
        elif all(score < -0.3 for score in scores[-3:]):
            distress = True
    
    logger.info(f"Threshold check complete. Distress detected: {distress}")

    return {"distress_detected": distress}


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


# 5. The LLM Node
def generate_nudge(state: AgentState) -> dict:
    """Uses Claude to write a highly personalised, empathetic nudge"""
    logger.info("Distress detected! Generating nudge with Claude...")

    # Initialise Claude
    llm = ChatAnthropic(model="claude-3-haiku-20240307", temperature=0.7)

    # Prompt Structure
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are a compassionate mental wellness companion trained in CBT techniques. "
                   "Never diagnose. Always validate. Suggest, don't prescribe. "
                   "Keep your response to exactly 3 warm, specific sentences containing one actionable suggestion."),
        ("user", "Here is the user's recent emotional data:\n"
                 "Mood History (last 7 days): {history}\n"
                 "Trajectory Math: {trajectory}\n\n"
                 "Write a supportive nudge for this user.")
    ])

    # Connect the prompt to the LLM
    chain = prompt | llm

    # Run Claude
    response = chain.invoke({
        "history": state["mood_history"],
        "trajectory": state["trajectory"]
    })

    # Decide the type of nudge based on the severity of the slope
    nudge_type = "cbt" if state["trajectory"]["slope"] < -0.2 else "breathing"

    return {
        "nudge_content": response.content,
        "nudge_type": nudge_type
    }


# 6. The Save Node
def send_nudge(state: AgentState) -> dict:
    """Saves the generated nudge to the database"""
    logger.info("Saving nudge to database...")

    with SyncSessionLocal() as db:
        # 1. Save to database
        new_nudge = Nudge(
            user_id = state['user_id'],
            nudge_type = state['nudge_type'],
            content = state['nudge_content'],
            trigger_reason = f"Agent detected negative slope of {state['trajectory']['slope']:.2f}"
        )
        db.add(new_nudge)

        # 2. Get the user's profile to find their name/email
        # (Assuming 'username' is an email for now, based on standard Supabase setups)
        user = db.query(UserProfile).filter(UserProfile.id == state['user_id'].first())

        if user and user.username:
            # Change "YOUR_RESEND_EMAIL@DOMAIN.COM" to the exact email you used to sign up for Resend!
            # Since you are on the free tier, you can only send test emails to yourself.
            target_email = "mnaumansiddiqui06@gmail.com" 
            
            # Fire the email!
            send_nudge_email(
                to_email=target_email,
                username=user.username.split('@')[0].capitalize(), 
                nudge_content=state['nudge_content']
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