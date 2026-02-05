from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from helpers.read_service import DocumentIntelligenceExtractor, TextCleaner
from helpers.indexacion import Chunker, EmbeddingService, AzureSearchIndexer
from helpers.ingestion import IngestionService
from core.rag_service import RAGService

router = APIRouter(prefix="/api/chat", tags=["chat"])

# Instancias (simple; luego puedes meter Depends)
extractor = DocumentIntelligenceExtractor()
cleaner = TextCleaner()
chunker = Chunker(max_tokens=900, overlap=150)
embedder = EmbeddingService()
indexer = AzureSearchIndexer()

ingestor = IngestionService(extractor, cleaner, chunker, embedder, indexer)
rag = RAGService(embedder, indexer)

ALLOWED_CT = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}

@router.post("/upload")
async def upload(
    files: list[UploadFile] = File(...),
    user_id: str = Form(...),
    session_id: str = Form(...),
):
    if not files:
        raise HTTPException(400, "Adjunta al menos 1 archivo.")
    if not user_id or not session_id:
        raise HTTPException(400, "user_id y session_id son requeridos.")

    results = []
    total_chunks = 0

    for f in files:
        file_bytes = await f.read()
        ct = f.content_type or ""
        name = f.filename or "archivo"

        if ct not in ALLOWED_CT:
            raise HTTPException(400, f"Tipo no permitido: {name} ({ct})")

        r = ingestor.ingest(
            file_bytes=file_bytes,
            content_type=ct,
            file_name=name,
            user_id=user_id,
            session_id=session_id,
        )
        results.append(r)
        total_chunks += r["chunks"]

    return {"files": results, "total_chunks": total_chunks}


@router.post("/ask")
async def ask(
    question: str = Form(...),
    user_id: str = Form(...),
    session_id: str = Form(...),
):
    if not question.strip():
        raise HTTPException(400, "question es requerida.")
    return rag.answer(question=question, user_id=user_id, session_id=session_id, top_k=6)
