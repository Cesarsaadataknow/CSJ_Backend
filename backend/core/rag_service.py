from collections import defaultdict
from openai import AzureOpenAI
from app.config import settings
from helpers.indexacion import EmbeddingService, AzureSearchIndexer, FabricSearchIndexer

class RAGService:
    def __init__(self, embedder: EmbeddingService, indexer: AzureSearchIndexer) -> None:
        self.embedder = embedder
        self.indexer = indexer
        self.chat = AzureOpenAI(
            api_key=settings.AZURE_OPENAI_KEY,
            azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
            api_version=settings.AZURE_OPENAI_OPENAI_VERSION,
        )

    def _is_per_document_request(self, question: str) -> bool:
        q = (question or "").lower()
        triggers = [
            "cada documento", "cada archivo", "por documento", "por archivo",
            "de que trata cada", "¿de qué trata cada", "resumen de cada", "resume cada"
        ]
        return any(t in q for t in triggers)

    def answer(self, question: str, user_id: str, session_id: str, top_k: int = 6) -> dict:
        if self._is_per_document_request(question):
            return self.answer_per_document(question, user_id, session_id)
        qvec = self.embedder.embed(question)
        hits = self.indexer.hybrid_search(
            question=question,
            query_vector=qvec,
            user_id=user_id,
            session_id=session_id,
            top_k=top_k
        )

        context = "\n\n".join(
            f"[{h.get('file_name')} | chunk {h.get('chunk_id')}] {h.get('content')}"
            for h in hits
        ).strip()

        system = (
            "Responde SOLO con base en el CONTEXTO. No inventes. "
            "Si no está en el contexto, responde: 'No encuentro esa información en el documento subido'."
        )

        user = f"CONTEXTO:\n{context}\n\nPREGUNTA:\n{question}"

        resp = self.chat.chat.completions.create(
            model=settings.AZURE_OPENAI_CHAT_DEPLOYMENT,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.2,
        )

        return {
            "answer": resp.choices[0].message.content,
            "chunks_used": [
                {"file_name": h.get("file_name"), "chunk_id": h.get("chunk_id"), "file_id": h.get("file_id")}
                for h in hits
            ],
        }

    def answer_per_document(self, question: str, user_id: str, session_id: str) -> dict:
        qvec = self.embedder.embed(question)
        files = self.indexer.list_session_files(user_id=user_id, session_id=session_id)
        if not files:
            return {"answer": "No encuentro documentos indexados en esta sesión.", "chunks_used": []}
        per_doc_hits = []
        grouped_context_parts = []

        for f in files:
            fid = f["file_id"]
            fname = f["file_name"]

            hits = self.indexer.hybrid_search_by_file(
                question=question,
                query_vector=qvec,
                user_id=user_id,
                session_id=session_id,
                file_id=fid,
                top_k=4
            )
            if not hits:
                grouped_context_parts.append(f"### {fname}\n- (Sin evidencia recuperada)")
                continue
            bullets = []
            for h in hits:
                bullets.append(f"- (chunk {h.get('chunk_id')}) {h.get('content','')}")
                per_doc_hits.append(h)

            grouped_context_parts.append(f"### {fname}\n" + "\n".join(bullets))

        context = "\n\n".join(grouped_context_parts).strip()

        system = (
            "El usuario subió varios documentos. "
            "Tu tarea es decir DE QUÉ TRATA CADA DOCUMENTO, usando SOLO el CONTEXTO.\n"
            "Formato obligatorio:\n"
            "- Documento: <nombre>\n"
            "  Resumen: <2-5 líneas>\n"
            "Si un documento no tiene evidencia suficiente, dilo claramente."
        )

        user = f"CONTEXTO (por documento):\n{context}\n\nPREGUNTA:\n{question}"
        resp = self.chat.chat.completions.create(
            model=settings.AZURE_OPENAI_CHAT_DEPLOYMENT,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.2,
        )

        return {
            "answer": resp.choices[0].message.content,
            "chunks_used": [
                {"file_name": h.get("file_name"), "chunk_id": h.get("chunk_id"), "file_id": h.get("file_id")}
                for h in per_doc_hits
            ],
        }

class RAGFabricService:
    def __init__(self, embedder: EmbeddingService, indexer: FabricSearchIndexer) -> None:
        self.embedder = embedder
        self.indexer = indexer
        self.chat = AzureOpenAI(
            api_key=settings.AZURE_OPENAI_KEY,
            azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
            api_version=settings.AZURE_OPENAI_OPENAI_VERSION,
        )

    def _hit_text(self, h: dict) -> str:
        if h.get("_source_index") == "fabric":
            return (h.get("TEXTOPROVIDENCIA") or "").strip()
        contenido = (h.get("contenido") or "").strip()
        regla = (h.get("regla") or "").strip()

        if regla and contenido:
            return f"REGLA: {regla}\nCONTENIDO: {contenido}"
        return contenido or regla

    def answer(self, question: str, top_k: int = 10) -> dict:
        qvec = self.embedder.embed(question)
        hits = self.indexer.hybrid_search(
            question=question,
            query_vector=qvec,
            top_k=top_k
        )

        print("################## HITS TOTAL (FABRIC+XLS): ###############################", len(hits))

        normalized = []
        for h in hits:
            d = dict(h)
            d["_text"] = self._hit_text(d)
            if d["_text"]:
                normalized.append(d)

        parts = []
        for h in normalized:
            if h.get("_source_index") == "fabric":
                parts.append(
                    f"[fabric | {h.get('tipo_documento','')} | {h.get('ACTOR','')} | chunk {h.get('chunk_order','')}] {h.get('_text','')}"
                )
            else:
                parts.append(
                    f"[xls | categoria={h.get('categoria','')} | tema={h.get('tema','')} | norma={h.get('norma_fuente','')}] {h.get('_text','')}"
                )

        context = "\n\n".join(parts).strip()

        system = (
            "Responde usando EXCLUSIVAMENTE la información del CONTEXTO (CORPUS).\n"
            "Puedes parafrasear y sintetizar.\n"
            "Si hay información relacionada aunque no use exactamente las mismas palabras, úsala.\n"
            "Solo responde que no encuentras información si realmente no existe contenido relacionado.\n"
            "No inventes datos fuera del contexto."
        )

        user = f"CONTEXTO:\n{context}\n\nPREGUNTA:\n{question}"

        resp = self.chat.chat.completions.create(
            model=settings.AZURE_OPENAI_CHAT_DEPLOYMENT,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.2,
        )

        return {
            "answer": resp.choices[0].message.content,
            "chunks_used": [
                {
                    "id": h.get("id"),
                    "source_index": h.get("_source_index"),
                }
                for h in normalized
            ],
        }

