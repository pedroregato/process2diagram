# services/file_ingest.py
from modules.ingest import load_transcript as original_load

def load_transcript(uploaded_file):
    """Wrapper para o load_transcript existente."""
    return original_load(uploaded_file)
