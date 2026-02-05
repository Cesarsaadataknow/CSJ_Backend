from __future__ import annotations
from typing import Optional, List, Any

class Tools:
    def __init__(self, rag_userdocs, rag_corpus, llm_chat):
        self.rag_userdocs = rag_userdocs
        self.rag_corpus = rag_corpus
        #self.downloader = downloader
        self.llm_chat = llm_chat

        self.user_id: Optional[str] = None
        self.session_id: Optional[str] = None
        self.files: List[Any] = []

    def bind_context(self, session_id: str, user_id: str, files=None):
        self.session_id = session_id
        self.user_id = user_id
        self.files = files or []

    # ---------------------------------------------------------------------
    # TOOL 1: Conversacional
    # ---------------------------------------------------------------------
    def tool_conversacional(self, query: str) -> str:
        resp = self.llm_chat.invoke(query)
        return getattr(resp, "content", str(resp)).strip()

    # ---------------------------------------------------------------------
    # TOOL 2: RAG sobre documentos adjuntos
    # ---------------------------------------------------------------------
    def tool_rag_userdocs(self, query: str) -> str:
        if not self.user_id or not self.session_id:
            return "No tengo user_id/session_id para buscar en documentos adjuntos."

        res = self.rag_userdocs.answer(
            question=query,
            user_id=self.user_id,
            session_id=self.session_id,
            top_k=12
        )
        return (res.get("answer") or "").strip()

    # ---------------------------------------------------------------------
    # TOOL 3: RAG sobre índice desde fabric
    # ---------------------------------------------------------------------
    def tool_rag_fabric(self, query: str) -> str:
        res = self.rag_corpus.answer(
            question=query,
            top_k=12
        )
        return (res.get("answer") or "").strip()

    # ---------------------------------------------------------------------
    # TOOL 4: Descargar / Generar Word (o PDF)
    # ---------------------------------------------------------------------
    # def tool_word(self, query: str) -> str:
    #     if not self.user_id or not self.session_id:
    #         return "No tengo user_id/session_id para generar el archivo."

    #     # Ajusta esto a tu implementación real
    #     out = self.downloader.generate(
    #         session_id=self.session_id,
    #         user_id=self.user_id,
    #         instructions=query,
    #         fmt="docx"  
    #     )
    #     return f"Listo. Archivo generado: {out}"
