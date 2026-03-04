# modules/ingest.py
import io


def load_transcript(uploaded_file) -> str:
    """Load transcript from Streamlit UploadedFile object."""
    return io.TextIOWrapper(uploaded_file, encoding="utf-8").read()
