import logging

logger = logging.getLogger(__name__)

class FusionModel:
    @staticmethod
    def calculate_text_valence(text_scores: dict) -> float:
        """
        Converts the 7 distinct text emotions into a single Valence score (-1.0 to 1.0).
        Uses averaged negative scores to prevent 4 negative categories from dominating,
        and dampens the result when neutral is the dominant signal.
        """
        positive_avg = (
            text_scores.get("joy", 0.0)
            + text_scores.get("love", 0.0)
            + text_scores.get("optimism", 0.0)
        ) / 3.0
        negative_avg = (
            text_scores.get("sadness", 0.0)
            + text_scores.get("anger", 0.0)
            + text_scores.get("fear", 0.0)
            + text_scores.get("disgust", 0.0)
        ) / 4.0
        neutral = text_scores.get("neutral", 0.0)

        raw_valence = positive_avg - negative_avg
        valence = raw_valence * (1.0 - 0.6 * neutral)
        return max(-1.0, min(1.0, valence))

    @staticmethod
    def fuse(text_scores: dict, voice_results: dict = None) -> float:
        """
        Combines Text Valence and Voice Valence using the PRD-specified MVP weights.
        """
        text_valence = FusionModel.calculate_text_valence(text_scores)

        # Fallback: If no audio exists (or voice analysis failed), rely 100% on text
        if not voice_results or "valence" not in voice_results or voice_results.get("valence") == 0.0:
            logger.info(f"Fusing: Audio missing/failed. Using 100% Text Valence ({text_valence})")
            return round(text_valence, 4)

        voice_valence = voice_results.get("valence", 0.0)

        # The exact math from Day 6 of the PRD:
        # (0.6 * text_valence) + (0.4 * voice_valence)
        fused_score = (0.6 * text_valence) + (0.4 * voice_valence)

        logger.info(f"Fusing: 60% Text ({text_valence}) + 40% Voice ({voice_valence}) = {fused_score}")
        
        # Clamp just in case, and round to 4 decimal places
        return round(max(-1.0, min(1.0, fused_score)), 4)