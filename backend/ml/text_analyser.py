import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification
import logging

logger = logging.getLogger(__name__)

class TextEmotionAnalyzer:
    def __init__(self, model_name: str = "your-username/moodmap-roberta"):
        self.model_name = model_name
        self.tokenizer = None,
        self.model = None

        # The exact 7 emotions we trainer the model on, in the same order
        self.emotions = ["joy", "sadness", "anger", "fear", "surprise", "disgust", "neutral"]

    def _load_model(self):
        """
        Lazy-loading: We only download and load the model into memory
        the very first time a user submits a journal entry.
        """
        if self.model is None or self.tokenizer is None:
            logger.info(f"Loading Text Emotion Model from Hugging Face: {self.model_name}...")
            try:
                self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
                self.model = AutoModelForSequenceClassification.from_pretrained(self.model)

                # Use CPU for inference. It's pretty fast for text (under 1s)
                self.device = torch.device("cpu")
                self.model.to(self.device)

                logger.info("Text Emotion Model loaded and cached successfully")
            except Exception as e:
                logger.error(f"Failed to load model {self.model_name}: {str(e)}")
                raise e
            
    def analyze(self, text: str) -> dict:
        """
        Takes raw journal text and returns a dictionary of emotion scores
        """
        if not text or not text.strip():
            raise ValueError("Cannot analyze empty text")
        
        # Ensure the model is loaded
        self._load_model()

        try:
            # 1. Translate the English text into numbers (Tokenization)
            inputs = self.tokenizer(
                text,
                return_tensors="pt",
                truncation=True,
                padding=True,
                max_length=512
            ).to(self.device)

            # 2. Run the numbers through the AI brain (inference)
            with torch.no_grad():
                outputs = self.model(**inputs)

            # 3. Convert the raw output into percentages between 0.0 and 1.0
            # We use sigmoid because we trained it using BCEWithLogitsLoss (multi-label)
            probabilities = torch.sigmoid(outputs.logits).squeeze().cpu().numpy()

            # 4. Map the percentages back to our emotion labels
            scores = {emotion: round(float(prob), 4) for emotion, prob in zip(self.emotions, probabilities)}

            # 5. Find the highest scoring emotion
            dominant_emotion = max(scores, key=scores.get)

            return {
                "scores": scores,
                "dominant_emotion": dominant_emotion
            }
        
        except Exception as e:
            logger.error(f"Error during text analysis: {str(e)}")
            # Safe fallback so the app doesn't crash if the AI glitches
            return {
                "scores": {e: 0.0 for e in self.emotions},
                "dominant_emotion": "neutral",
                "error": str(e)
            }