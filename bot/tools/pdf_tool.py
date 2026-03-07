import io
from pypdf import PdfReader

def extract_pdf_text(file_bytes: bytes) -> str:
    """Extract text from a PDF file. Returns up to 8000 characters."""
    try:
        reader = PdfReader(io.BytesIO(file_bytes))
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
        return text[:8000]
    except Exception as e:
        return f"Could not read PDF: {e}"
