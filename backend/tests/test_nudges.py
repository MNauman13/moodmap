import pytest
from backend.routers.nudges import update_intervention_weights

def test_update_weights_helpful():
    """If a user gives a thumbs up (1), that intervention's weight should increase."""
    initial_weights = {"breathing": 0.2, "cbt": 0.2, "physical": 0.2, "social": 0.2, "referral": 0.2}
    
    # User liked the breathing exercise
    new_weights = update_intervention_weights(initial_weights, "breathing", 1)
    
    assert new_weights["breathing"] > 0.2
    # The math normalizes it, so the total should still be exactly 1.0 (100%)
    assert sum(new_weights.values()) == pytest.approx(1.0, abs=0.001)

def test_update_weights_not_helpful():
    """If a user gives a thumbs down (-1), that intervention's weight should decrease."""
    initial_weights = {"breathing": 0.2, "cbt": 0.2, "physical": 0.2, "social": 0.2, "referral": 0.2}
    
    # User hated the CBT exercise
    new_weights = update_intervention_weights(initial_weights, "cbt", -1)
    
    assert new_weights["cbt"] < 0.2
    assert sum(new_weights.values()) == pytest.approx(1.0, abs=0.001)