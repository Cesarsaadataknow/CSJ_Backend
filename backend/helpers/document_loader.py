from io import BytesIO
from fastapi import UploadFile
import fitz  # PyMuPDF
from docx import Document

async def extract_text_from_file(file: UploadFile) -> str:
    content = await file.read()
    filename = file.filename.lower()

    if filename.endswith(".pdf"):
        return extract_text_pdf(content)

    elif filename.endswith(".docx"):
        return extract_text_docx(content)

    else:
        raise ValueError("Formato no soportado. Solo PDF y DOCX.")

def extract_text_pdf(content: bytes) -> str:
    text = ""
    with fitz.open(stream=content, filetype="pdf") as pdf:
        for page in pdf:
            text += page.get_text()
    return text.strip()

def extract_text_docx(content: bytes) -> str:
    doc = Document(BytesIO(content))
    return "\n".join([p.text for p in doc.paragraphs]).strip()
