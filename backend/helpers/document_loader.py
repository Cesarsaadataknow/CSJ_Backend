import fitz
import docx

def load_pdf(file_bytes: bytes) -> str:
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    return "\n".join(page.get_text() for page in doc)

def load_docx(file_bytes: bytes) -> str:
    document = docx.Document(file_bytes)
    return "\n".join(p.text for p in document.paragraphs)

def simple_chunk(text: str, size: int = 1200, overlap: int = 150):
    chunks = []
    start = 0
    while start < len(text):
        end = start + size
        chunks.append(text[start:end])
        start = end - overlap
    return chunks
