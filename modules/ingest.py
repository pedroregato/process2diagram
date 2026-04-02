# modules/ingest.py
import io
from pathlib import Path

def load_transcript(uploaded_file) -> str:
    """
    Load transcript from uploaded file (supports .txt, .docx, .pdf).
    Returns the extracted text as a string.
    """
    filename = uploaded_file.name.lower()
    
    # --- .txt: plain text with UTF-8 fallback ---
    if filename.endswith('.txt'):
        try:
            return uploaded_file.read().decode('utf-8')
        except UnicodeDecodeError:
            # fallback to latin-1 (common for Windows exports)
            uploaded_file.seek(0)
            return uploaded_file.read().decode('latin-1')
    
    # --- .docx: use python-docx ---
    elif filename.endswith('.docx'):
        try:
            import docx
            doc = docx.Document(uploaded_file)
            full_text = []
            for para in doc.paragraphs:
                full_text.append(para.text)
            return '\n'.join(full_text)
        except ImportError:
            raise ImportError("python-docx is required for .docx files. Install with: pip install python-docx")
        except Exception as e:
            raise RuntimeError(f"Failed to parse .docx file: {e}")
    
    # --- .pdf: use pypdf (or PyPDF2) ---
    elif filename.endswith('.pdf'):
        try:
            from pypdf import PdfReader
            # If pypdf not available, try PyPDF2
        except ImportError:
            try:
                from PyPDF2 import PdfReader
            except ImportError:
                raise ImportError("pypdf or PyPDF2 is required for .pdf files. Install with: pip install pypdf")
        
        try:
            reader = PdfReader(uploaded_file)
            full_text = []
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    full_text.append(text)
            return '\n'.join(full_text)
        except Exception as e:
            raise RuntimeError(f"Failed to parse .pdf file: {e}")
    
    else:
        raise ValueError(f"Unsupported file type: {filename}. Please upload .txt, .docx, or .pdf.")
