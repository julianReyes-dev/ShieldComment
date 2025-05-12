from typing import Dict
import logging

logger = logging.getLogger(__name__)

async def analyze_toxicity(comment_text: str) -> Dict:
    """
    Simplified toxicity analyzer that can be replaced with a real ML model.
    For production, replace with unitary/toxic-bert or similar.
    """
    try:
        toxic_words = ["idiota", "estúpido", "imbécil", "tonto", "mierda"]
        toxic_count = sum(1 for word in toxic_words if word in comment_text.lower())
        
        # Simple scoring logic (replace with actual model in production)
        toxicity_score = min(100, toxic_count * 30)
        
        if toxicity_score > 70:
            classification = "toxic"
        elif toxicity_score > 30:
            classification = "potentially-toxic"
        else:
            classification = "non-toxic"
        
        return {
            "toxicity_score": toxicity_score,
            "classification": classification,
            "details": {
                "toxic_words_found": toxic_count,
                "model_version": "mock-v1"
            }
        }
    except Exception as e:
        logger.error(f"Error in toxicity analysis: {e}")
        return {
            "toxicity_score": 0,
            "classification": "error",
            "details": {
                "error": str(e)
            }
        }