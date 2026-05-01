import torch
import torch.nn.functional as F
import librosa
import numpy as np
import logging
from transformers import AutoFeatureExtractor, HubertForSequenceClassification

logger = logging.getLogger(__name__)

VOICE_EMOTIONS = ["happy", "sad", "angry", "fearful", "disgust", "surprised", "neutral"]

VOICE_TO_MOODMAP = {
    "happy": "joy",
    "sad": "sadness",
    "angry": "anger",
    "fearful": "fear",
    "disgust": "disgust",
    "surprised": "surprise",
    "neutral": "neutral",
}

MOODMAP_EMOTIONS = ["joy", "love", "optimism", "sadness", "anger", "fear", "disgust", "surprise", "neutral"]

HIGH_AROUSAL = {"angry", "fearful", "surprised", "happy"}
LOW_AROUSAL = {"sad", "neutral", "disgust"}


class VoiceEmotionAnalyzer:
    def __init__(self, model_name: str = "MNauman13/moodmap-huberta"):
        self.model_name = model_name
        self.feature_extractor = None
        self.model = None

    def _load_model(self):
        if self.model is None or self.feature_extractor is None:
            logger.info(f"Loading Voice Emotion Model from Hugging Face: {self.model_name}...")
            try:
                self.feature_extractor = AutoFeatureExtractor.from_pretrained(self.model_name)
                self.model = HubertForSequenceClassification.from_pretrained(self.model_name)

                self.device = torch.device("cpu")
                self.model.to(self.device)

                logger.info("Voice Emotion Model loaded successfully")
            except Exception as e:
                logger.error(f"Failed to load voice model {self.model_name}: {str(e)}")
                raise e

    def analyze(self, audio_file_path: str) -> dict:
        self._load_model()

        try:
            audio_array, _ = librosa.load(audio_file_path, sr=16000)

            inputs = self.feature_extractor(
                audio_array,
                sampling_rate=16000,
                return_tensors="pt",
                padding=True,
            ).to(self.device)

            with torch.no_grad():
                outputs = self.model(**inputs)

            probs = F.softmax(outputs.logits, dim=-1).squeeze().cpu().numpy()
            voice_scores = {VOICE_EMOTIONS[i]: float(probs[i]) for i in range(len(VOICE_EMOTIONS))}

            mapped_scores = {e: 0.0 for e in MOODMAP_EMOTIONS}
            for v_emo, score in voice_scores.items():
                mapped_scores[VOICE_TO_MOODMAP[v_emo]] = score

            positive_avg = (mapped_scores["joy"] + mapped_scores["love"] + mapped_scores["optimism"]) / 3.0
            negative_avg = (
                mapped_scores["sadness"] + mapped_scores["anger"]
                + mapped_scores["fear"] + mapped_scores["disgust"]
            ) / 4.0
            neutral = mapped_scores["neutral"]
            valence = (positive_avg - negative_avg) * (1.0 - 0.6 * neutral)
            valence = max(-1.0, min(1.0, valence))

            arousal = sum(voice_scores.get(e, 0.0) for e in HIGH_AROUSAL) - \
                      sum(voice_scores.get(e, 0.0) for e in LOW_AROUSAL)
            arousal = max(-1.0, min(1.0, arousal))

            energy = float(np.sqrt(np.mean(audio_array**2)))

            return {
                "valence": round(valence, 4),
                "arousal": round(arousal, 4),
                "energy": round(energy, 4),
            }
        except Exception as e:
            logger.error(f"Error during voice analysis: {str(e)}")
            return {
                "valence": 0.0,
                "arousal": 0.0,
                "energy": 0.0,
                "error": str(e),
            }
