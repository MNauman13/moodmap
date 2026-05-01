import pytest
from backend.ml.fusion import FusionModel

def test_calculate_text_valence_positive():
    """Strongly positive entry should produce positive valence."""
    scores = {"joy": 0.8, "love": 0.3, "optimism": 0.5, "sadness": 0.05, "anger": 0.0, "fear": 0.0, "disgust": 0.0, "neutral": 0.1}
    valence = FusionModel.calculate_text_valence(scores)
    assert valence > 0.4

def test_calculate_text_valence_neutral_dampens():
    """High neutral score should push valence toward zero."""
    scores = {"joy": 0.1, "love": 0.05, "optimism": 0.05, "sadness": 0.1, "anger": 0.05, "fear": 0.05, "disgust": 0.3, "neutral": 0.7}
    valence = FusionModel.calculate_text_valence(scores)
    assert -0.1 < valence < 0.1

def test_calculate_text_valence_clamped():
    """Extreme negatives should clamp at -1.0."""
    scores = {"joy": 0.0, "love": 0.0, "optimism": 0.0, "anger": 0.9, "sadness": 0.9, "fear": 0.9, "disgust": 0.9, "neutral": 0.0}
    valence = FusionModel.calculate_text_valence(scores)
    assert valence == -0.9

def test_calculate_text_valence_boring_day_not_extreme():
    """A boring/average journal entry must NOT produce distress-level scores."""
    scores = {"joy": 0.08, "love": 0.04, "optimism": 0.05, "sadness": 0.15, "anger": 0.12, "fear": 0.08, "disgust": 0.55, "surprise": 0.06, "neutral": 0.65}
    valence = FusionModel.calculate_text_valence(scores)
    assert valence > -0.6, f"Boring day scored {valence}, would falsely trigger distress agent"

def test_multimodal_fusion_with_audio():
    """Test the exact 60/40 text/voice weighting logic."""
    text_scores = {"joy": 1.0, "love": 1.0, "optimism": 1.0, "sadness": 0.0, "anger": 0.0, "fear": 0.0, "disgust": 0.0, "neutral": 0.0}
    voice_results = {"valence": -0.5}

    fused = FusionModel.fuse(text_scores, voice_results)
    assert fused == 0.4

def test_multimodal_fusion_audio_fallback():
    """If audio fails or is missing, fall back to 100% text."""
    text_scores = {"joy": 0.0, "love": 0.0, "optimism": 0.0, "sadness": 0.5, "anger": 0.0, "fear": 0.0, "disgust": 0.0, "neutral": 0.0}
    voice_results = {"error": "File unreadable"}

    fused = FusionModel.fuse(text_scores, voice_results)
    assert fused == pytest.approx(-0.125, abs=0.01)

def test_balanced_emotions_near_zero():
    """Equal positive and negative signals should produce near-zero valence."""
    scores = {"joy": 0.5, "love": 0.5, "optimism": 0.5, "sadness": 0.5, "anger": 0.5, "fear": 0.5, "disgust": 0.5, "neutral": 0.0}
    valence = FusionModel.calculate_text_valence(scores)
    assert -0.1 < valence < 0.1
