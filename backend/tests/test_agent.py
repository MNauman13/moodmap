import pytest
from unittest.mock import patch, MagicMock
from backend.agents.distress_agent import compute_trajectory, check_threshold, generate_nudge

def test_compute_trajectory_severe_drop():
    """Test that our numpy math correctly identifies a downward slope."""
    # A user whose mood is crashing over 7 days
    state = {"user_id": "123", "mood_history": [0.8, 0.6, 0.4, 0.2, 0.0, -0.4, -0.8]}
    
    result = compute_trajectory(state)
    
    assert "trajectory" in result
    assert result["trajectory"]["slope"] < -0.15 # It should detect a severe negative slope

def test_check_threshold_triggers_distress():
    """Test that the decision node properly flags a user in danger."""
    state = {
        "mood_history": [0.8, 0.6, 0.4, 0.2, 0.0, -0.4, -0.8],
        "trajectory": {"slope": -0.25, "volatility": 0.4, "z_score": -2.0}
    }
    
    result = check_threshold(state)
    assert result["distress_detected"] is True

# 🚨 THE ULTIMATE MOCK 🚨
# We patch out the database AND the Anthropic LLM
@patch('backend.agents.distress_agent.SyncSessionLocal')
@patch('backend.agents.distress_agent.ChatAnthropic')
def test_generate_nudge(mock_anthropic_class, mock_db):
    """Test that the agent formulates a prompt and gets a response without actually calling Claude."""
    
    # 1. Fake the Claude API Response
    mock_llm_instance = MagicMock()
    mock_anthropic_class.return_value = mock_llm_instance
    mock_llm_instance.invoke.return_value.content = "Take a deep breath and count to ten."
    mock_llm_instance.return_value.content = "Take a deep breath and count to ten."
    
    # 2. Fake the Database Session
    mock_session = MagicMock()
    mock_db.return_value.__enter__.return_value = mock_session
    mock_session.query().filter().first.return_value = None # Simulate a user with no custom weights yet
    
    state = {
        "user_id": "fake-user-uuid",
        "mood_history": [-0.5, -0.6, -0.8],
        "trajectory": {"slope": -0.2, "volatility": 0.1, "z_score": -1.5}
    }
    
    # Run the node
    result = generate_nudge(state)
    
    # Assertions
    assert "nudge_content" in result
    assert result["nudge_content"] == "Take a deep breath and count to ten."
    assert "nudge_type" in result