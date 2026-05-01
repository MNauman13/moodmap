import os
import torch
import logging
from transformers import RobertaForSequenceClassification, AutoTokenizer

logger = logging.getLogger(__name__)

class TextEmotionAnalyzer:
    def __init__(self, model_name: str = "MNauman13/moodmap-roberta"):
        self.model_name = model_name
        self.tokenizer = None
        self.model = None

    def _load_model(self):
        """Lazy load the NLP model only when needed."""
        if self.model is None or self.tokenizer is None:
            logger.info(f"Loading Text Emotion Model from Hugging Face: {self.model_name}...")
            
            # Grab the Hugging Face token from environment variables (if it exists)
            hf_token = os.getenv("HF_TOKEN")
            
            try:
                # Explicitly pass the model_name to BOTH the tokenizer and the model
                self.tokenizer = AutoTokenizer.from_pretrained(
                    self.model_name,
                    token=hf_token
                )
                self.model = RobertaForSequenceClassification.from_pretrained(
                    self.model_name, 
                    token=hf_token
                )
                
                self.device = torch.device("cpu")
                self.model.to(self.device)
                
                logger.info("✅ Text Emotion Model loaded successfully!")
            except Exception as e:
                logger.error(f"Failed to load model {self.model_name}: {str(e)}")
                raise e

    def analyze(self, text: str) -> dict:
        self._load_model()
        
        try:
            inputs = self.tokenizer(
                text, 
                return_tensors="pt", 
                truncation=True, 
                padding=True, 
                max_length=128
            ).to(self.device)

            with torch.no_grad():
                outputs = self.model(**inputs)

            # Apply sigmoid because we used multi-label classification during training
            scores = torch.sigmoid(outputs.logits).squeeze().cpu().numpy()

            # Map the 9 scores to their exact emotion labels (must match training order)
            emotions = ["joy", "love", "optimism", "sadness", "anger", "fear", "disgust", "surprise", "neutral"]
            results = {emotions[i]: float(scores[i]) for i in range(len(emotions))}

            # Find the highest scoring emotion
            dominant_emotion = max(results, key=results.get)

            return {
                "scores": results,
                "dominant_emotion": dominant_emotion
            }
        except Exception as e:
            logger.error(f"Error during text analysis: {str(e)}")
            return {"error": str(e)}