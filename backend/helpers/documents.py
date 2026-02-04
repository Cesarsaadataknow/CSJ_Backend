from fastapi import APIRouter, UploadFile, File, HTTPException
from helpers.document_loader import extract_text_from_file
from helpers.chunker import chunk_text
from helpers.indexer_docs import index_document  # índice uploaded-docs-index

documents_router = APIRouter(prefix="/documents", tags=["Documents"])

@documents_router.post("/upload")
async def upload_document(file: UploadFile = File(...)):
    try:
        text = await extract_text_from_file(file)

        if not text.strip():
            raise HTTPException(
                status_code=400,
                detail="El documento no contiene texto legible"
            )

        # 🔹 Chunking
        chunks = chunk_text(text)

        # 🔹 Indexar chunks
        document_id = index_document_chunks(
            chunks=chunks,
            filename=file.filename
        )

        return {
            "status": "ok",
            "document_id": document_id,
            "filename": file.filename,
            "chunks_indexed": len(chunks),
            "chars_total": len(text)
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# @documents_router.post("/upload")
# async def upload_document(file: UploadFile = File(...)):
#     try:
#         # 1️⃣ Extraer texto del documento
#         text = await extract_text_from_file(file)

#         if not text or not text.strip():
#             raise HTTPException(
#                 status_code=400,
#                 detail="El documento no contiene texto legible"
#             )

#         # 2️⃣ Chunking
#         chunks = chunk_text(text)

#         if not chunks:
#             raise HTTPException(
#                 status_code=400,
#                 detail="No fue posible dividir el documento en fragmentos"
#             )

#         # 3️⃣ Indexar cada chunk
#         indexed_chunks = []

#         for i, chunk in enumerate(chunks):
#             doc_id = index_document(
#                 content=chunk,
#                 filename=file.filename,
#                 metadata={
#                     "chunk_id": i,
#                     "total_chunks": len(chunks)
#                 }
#             )
#             indexed_chunks.append(doc_id)

#         # 4️⃣ Respuesta
#         return {
#             "status": "ok",
#             "filename": file.filename,
#             "chunks_indexed": len(indexed_chunks),
#             "chars_total": len(text)
#         }

#     except HTTPException:
#         raise
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))
