import uuid
from datetime import datetime, timezone

from helpers.read_service import DocumentIntelligenceExtractor, TextCleaner
from helpers.indexacion import Chunker, EmbeddingService, AzureSearchIndexer


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
        
        document = self.extractor.extract_document(file_bytes, content_type)

        pages = document.get("pages", [])
        if not pages:
            return {"file_name": file_name, "file_id": None, "chunks": 0}

        file_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)

        docs: list[dict] = []
        total_chunks = 0
        pages_with_ai = 0
        complex_tables_count = 0

        for page in pages:
            page_number = page.get("page_number")
            page_text = self.cleaner.clean(page.get("text", ""))

            if not page_text:
                continue

            page_needs_ai = bool(page.get("needs_ai", False))
            ai_reason = page.get("ai_reason", "")
            visual_description = page.get("visual_description", "")

            tables = page.get("tables", []) or []
            figures = page.get("figures", []) or []

            page_has_complex_table = any(
                t.get("table_type") == "complex" for t in tables
            )
            page_tables_marked_for_ai = any(
                t.get("needs_ai", False) for t in tables
            )

            if page_needs_ai:
                pages_with_ai += 1

            complex_tables_count += sum(
                1 for t in tables if t.get("table_type") == "complex"
            )

            chunks = self.chunker.split(page_text)

            for i, ch in enumerate(chunks):
                vec = self.embedder.embed(ch)

                docs.append(
                    {
                        "id": str(uuid.uuid4()),
                        "user_id": user_id,
                        "session_id": session_id,
                        "file_id": file_id,
                        "file_name": file_name,
                        "chunk_id": total_chunks,
                        "page_number": page_number,
                        "content": ch,
                        "content_vector": vec,
                        "created_at": now,

                        # metadatos útiles para retrieval
                        "needs_ai": page_needs_ai,
                        "ai_reason": ai_reason,
                        "has_visual_description": bool(visual_description),
                        "has_figures": len(figures) > 0,
                        "figures_count": len(figures),
                        "tables_count": len(tables),
                        "has_complex_table": page_has_complex_table,
                        "tables_marked_for_ai": page_tables_marked_for_ai,
                        "page_context_preview": page_text[:1000],
                    }
                )
                total_chunks += 1

        if not docs:
            return {"file_name": file_name, "file_id": None, "chunks": 0}

        self.indexer.upload(docs)

        return {
            "file_name": file_name,
            "file_id": file_id,
            "chunks": len(docs),
            "pages": len(pages),
            "pages_marked_for_ai": pages_with_ai,
            "complex_tables_count": complex_tables_count,
        }