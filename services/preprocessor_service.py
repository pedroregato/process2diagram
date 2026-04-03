# services/preprocessor_service.py
from modules.transcript_preprocessor import preprocess

def preprocess_transcript(text: str):
    """Encapsula o pré-processador para uso na UI."""
    return preprocess(text)
