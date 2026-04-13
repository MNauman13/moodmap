import torch
import librosa
import numpy as np
import logging
from transformers import Wav2Vec2Processor, Wav2Vec2ForSequenceClassification

logger = logging.getLogger(__name__)

class VoiceEmotionAnalyzer:
    def __init__(self, model_name: str = "MNauman13/moodmap-wav2vec2"):
        self.model_name = model_name
        self.processor = None
        self.model = None

    def _load_model(self):
        """
        Lazy load the massive audio mode only when a voice note
        is actually submitted
        """
        if self.model is None or self.processor is None:
            logger.info(f"Loading Voice Emotion Model from Hugging Face: {self.model_name}...")
            try:
                # The processor converts sound waves into numbers
                self.processor = Wav2Vec2Processor.from_pretrained("facebook/wav2vec2-base")
                # The model makes the emotional predictions
                self.model = Wav2Vec2ForSequenceClassification.from_pretrained(self.model_name)

                self.device = torch.device("cpu")
                self.model.to(self.device)

                logger.info("Voice Emotion Model loaded successfully")
            except Exception as e:
                logger.error(f"Failed to load voice model {self.model_name}: {str(e)}")
                raise e
            
    def analyze(self, audio_file_path: str) -> dict:
        """
        Takes a local audio file path (.wav or .webm) and returns
        emotional dimensions
        """
        self._load_model()

        try:
            # 1. Load the audio file. Wav2Vec2 strictly requires a 16KHz sample rate
            # librosa automatically converts any format (webm, mp3, wav) to 16KHz mono
            audio_array, _ = librosa.load(audio_file_path, sr=16000)

            # 2. Convert the raw audio wave into the exact tensor format the AI expects
            inputs = self.processor(
                audio_array,
                sampling_rate=16000,
                return_tensors="pt",
                padding=True
            ).to(self.device)

            # 3. Run the audio through the brain
            with torch.no_grad():
                outputs = self.model(**inputs)

            # 4. Extract the continuous regression scores
            # Index 0 = Valence (Negative to Positive)
            # Index 1 = Arousal (Low Energy to High Energy)
            predictions = outputs.logits.squeeze().cpu().numpy()

            valence = float(predictions[0])
            arousal = float(predictions[1])

            # Safely clamp to ensure numbers stay between -1.0 and 1.0
            valence = max(-1.0, min(1.0, valence))
            arousal = max(-1.0, min(1.0, arousal))

            # 5. Calculate pure acoustic energy (Volume/Intensity) using standard math (RMS)
            energy = float(np.sqrt(np.mean(audio_array**2)))

            return {
                "valence": round(valence, 4),
                "arousal": round(arousal, 4),
                "energy": round(energy, 4)
            }
        except Exception as e:
            logger.error(f"Error during voice analysis: {str(e)}")
            # Safe fallback
            return {
                "valence": 0.0,
                "arousal": 0.0,
                "energy": 0.0,
                "error": str(e)
            }