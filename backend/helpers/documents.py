from fastapi import APIRouter, UploadFile, File, HTTPException

from helpers.document_loader import extract_text_from_file
from helpers.indexer import index_document

documents_router = APIRouter()

@documents_router.post("/upload")
async def upload_document(file: UploadFile = File(...)):
    try:
        # 1️⃣ Extraer texto del archivo (docx, pdf, etc.)
        text = await extract_text_from_file(file)

        if not text.strip():
            raise HTTPException(
                status_code=400,
                detail="El documento no contiene texto legible"
            )

        # 2️⃣ Indexar documento (el ID se genera dentro del indexer)
        index_document(text)

        # 3️⃣ Respuesta
        return {
            "status": "ok",
            "filename": file.filename,
            "chars_indexed": len(text)
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
