import pytest
from backend.ml.fusion import FusionModel

def test_calculate_text_valence_positive():
    """Test that positive emotions accurately calculate a high valence"""
    scores = {"joy": 0.8, "surprise": 0.1, "sadness": 0.05}
    valence = FusionModel.calculate_text_valence(scores)
    assert valence == 0.85

def test_calculate_text_valence_clamped():
    """Test that extreme emotions do not break the -1.0 to 1.0 boundary"""
    scores = {"anger": 0.8, "sadness": 0.9, "fear": 0.5} # Total negative weight = 2.2
    valence = FusionModel.calculate_text_valence(scores)
    assert valence == -1.0  # It should clamp safely at -1.0

def test_multimodal_fusion_with_audio():
    """Test the exact 60/40 text/voice weighting logic."""
    text_scores = {"joy": 1.0}  # Text valence = 1.0
    voice_results = {"valence": -0.5}

    # Expected: (0.6 * 1.0) + (0.4 * -0.5) = 0.6 - 0.2 = 0.4
    fused = FusionModel.fuse(text_scores, voice_results)
    assert fused == 0.4

def test_multimodal_fusion_audio_fallback():
    """Test that if audio fails or is missing, it falls back to 100% text"""
    text_scores = {"sadness": 0.5}  # Text valence = -0.5
    voice_results = {"error": "File unreadable"}

    fused = FusionModel.fuse(text_scores, voice_results)
    assert fused == -0.5