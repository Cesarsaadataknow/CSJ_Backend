# -----------------------------------------------------------------------------
# region           IMPORTACIONES
# -----------------------------------------------------------------------------
from __future__ import annotations
import os
import json
import uuid
from datetime import datetime
from typing import Optional, List, Any
#endregion

# -----------------------------------------------------------------------------
# region           CLASE FUNCIONES GENERALES
# -----------------------------------------------------------------------------
class Tools:
    # ---------------------------------------------------------------------
    # Funciones de inicializacion
    # ---------------------------------------------------------------------
    def __init__(self, rag_userdocs, rag_corpus, llm_chat, doc_generator, cosmosdb):
        self.rag_userdocs = rag_userdocs
        self.rag_corpus = rag_corpus
        self.doc_generator = doc_generator
        self.llm_chat = llm_chat
        self.cosmosdb = cosmosdb

        self.user_id: Optional[str] = None
        self.session_id: Optional[str] = None
        self.files: List[Any] = []

    # ---------------------------------------------------------------------
    # Funcion de contexto agente
    # ---------------------------------------------------------------------
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
    # TOOL 4: Descargar / Generar Word 
    # ---------------------------------------------------------------------
    def tool_word(self, instrucciones: str) -> str:
        """
        Genera DOCX con template y lo deja listo para descargar vía endpoint.
        Guarda el DOCX (bytes) en Cosmos (recomendado para ahora).
        """
        if not self.session_id or not self.user_id:
            return json.dumps({"ok": False, "message": "No hay session_id/user_id en contexto."})

        instrucciones = (instrucciones or "").strip()
        if not instrucciones:
            return json.dumps({"ok": False, "message": "Faltan instrucciones para generar el documento."})

        docx_bytes, payload = self.doc_generator.generate_docx_bytes(
            instrucciones=instrucciones,
            user_id=self.user_id,
            session_id=self.session_id,
            source=None,
        )

        filename = f"documento_{self.session_id}_{uuid.uuid4().hex[:8]}.docx"
        saved = self.cosmosdb.save_generated_doc(
            session_id=self.session_id,
            user_id=self.user_id,
            file_name=filename,
            docx_bytes=docx_bytes,
            payload=payload,
            message_id=None,  
        )

        doc_id = saved["id"]
        return {
            "ok": True,
            "message": "Listo, generé el documento. Dale por favor en Descargar.",
            "doc_id": doc_id,
            "file_name": filename,
            "session_id": self.session_id,
            "download_url": f"/api/chat/download/doc/{doc_id}",
        }
#endregion