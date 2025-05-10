import uuid 
from llama_index.core.settings import Settings
import logging  
import math

logger=logging.getLogger(__name__)

def generate_stable_id(identifier: str) -> str:
    """Generate a UUID5 based on a file path (stable across runs)."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, identifier))

def get_embedding(text: str) -> list[float]:
    if not text or not text.strip():
        return []

    embedding = Settings.embed_model.get_text_embedding(text)
    if not isinstance(embedding, list):
        embedding = embedding.tolist()

    if not all(isinstance(x, (float, int)) and math.isfinite(x) for x in embedding):
        logger.warning("Embedding contains non-finite values. Skipping embedding.")
        return []

    return embedding