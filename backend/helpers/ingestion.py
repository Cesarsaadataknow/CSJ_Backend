import uuid
from datetime import datetime, timezone
from helpers.read_service import DocumentIntelligenceExtractor, TextCleaner
from helpers.indexacion import Chunker,EmbeddingService,AzureSearchIndexer

class IngestionService:
    def __init__(
        self,
        extractor: DocumentIntelligenceExtractor,
        cleaner: TextCleaner,
        chunker: Chunker,
        embedder: EmbeddingService,
        indexer: AzureSearchIndexer,
    ) -> None:
        self.extractor = extractor
        self.cleaner = cleaner
        self.chunker = chunker
        self.embedder = embedder
        self.indexer = indexer

    def ingest(
        self,
        file_bytes: bytes,
        content_type: str,
        file_name: str,
        user_id: str,
        session_id: str,
    ) -> dict:
        raw_text = self.extractor.extract_text(file_bytes, content_type)
        text = self.cleaner.clean(raw_text)

        if not text:
            return {"file_name": file_name, "file_id": None, "chunks": 0}

        chunks = self.chunker.split(text)
        file_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)

        docs: list[dict] = []
        for i, ch in enumerate(chunks):
            vec = self.embedder.embed(ch)
            docs.append({
                "id": str(uuid.uuid4()),
                "user_id": user_id,
                "session_id": session_id,
                "file_id": file_id,
                "file_name": file_name,
                "chunk_id": i,
                "content": ch,
                "content_vector": vec,
                "created_at": now,
            })

        self.indexer.upload(docs)
        return {"file_name": file_name, "file_id": file_id, "chunks": len(chunks)}
