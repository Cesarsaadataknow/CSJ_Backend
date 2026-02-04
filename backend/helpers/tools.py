# helpers/tools.py

import re
import json
import asyncio
from typing import Optional, List
from fastapi import UploadFile
from dotenv import load_dotenv, find_dotenv

from app.config import settings
from langchain_openai import AzureChatOpenAI
from langchain.schema import HumanMessage

from helpers.principal_function import _process_chat

load_dotenv(find_dotenv(), override=True)


class Tools:
    def __init__(self):
        self.chat = AzureChatOpenAI(
            api_key=settings.AZURE_OPENAI_KEY,
            azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
            api_version=settings.AZURE_OPENAI_OPENAI_VERSION,
            deployment_name=settings.AZURE_OPENAI_CHAT_DEPLOYMENT,
            temperature=0.7,
        )

        self._session_id: Optional[str] = None
        self._user_id: Optional[str] = None
        self._files: Optional[List[UploadFile]] = None

    # ------------------------------------------------------------------
    # Contexto
    # ------------------------------------------------------------------
    def bind_context(
        self,
        session_id: Optional[str],
        user_id: Optional[str],
        files: Optional[List[UploadFile]],
    ) -> None:
        self._session_id = session_id
        self._user_id = user_id
        self._files = files

    # ------------------------------------------------------------------
    # Utilidades
    # ------------------------------------------------------------------
    def _extract_last_user_question(self, text: str) -> str:
        if not text:
            return ""
        m = re.search(
            r"<usuario>:\s*(.*?)\n<asistente>:\s*$",
            text,
            flags=re.DOTALL | re.IGNORECASE,
        )
        if m:
            return (m.group(1) or "").strip()
        return text.strip()

    def _decide_mode(self, question: str) -> str:
        """
        Regla segura:
        - answer por defecto
        - providencia SOLO si el usuario lo pide explícitamente
        """
        q = (question or "").lower()

        explicit_doc_requests = [
            "genera el documento",
            "generar el documento",
            "crear el documento",
            "descargar el documento",
            "generar word",
            "descargar word",
            "generar providencia",
            "haz la providencia",
        ]

        if any(k in q for k in explicit_doc_requests):
            return "providencia"

        return "answer"

    # ------------------------------------------------------------------
    # TOOL RAG
    # ------------------------------------------------------------------
    def tool_rag(self, query: str) -> str:
        if not self._session_id or not self._user_id:
            return "No se pudo identificar la sesión o el usuario."

        question = self._extract_last_user_question(query)
        mode = self._decide_mode(question)

        # 🔥 FIX CRÍTICO: no usar asyncio.run si ya hay loop
        try:
            loop = asyncio.get_running_loop()
            result = loop.run_until_complete(
                _process_chat(
                    question=question,
                    files=self._files,
                    session_id=self._session_id,
                    user_id=self._user_id,
                    mode=mode,
                )
            )
        except RuntimeError:
            result = asyncio.run(
                _process_chat(
                    question=question,
                    files=self._files,
                    session_id=self._session_id,
                    user_id=self._user_id,
                    mode=mode,
                )
            )

        answer = result.get("answer")

        if isinstance(answer, dict):
            return json.dumps(answer, ensure_ascii=False, indent=2)

        return str(answer or "").strip()

    # ------------------------------------------------------------------
    # TOOL CONVERSACIONAL
    # ------------------------------------------------------------------
    def tool_conversacional(self, prompt: str) -> str:
        if self._files:
            filenames = ", ".join(f.filename for f in self._files if f.filename)
            return (
                f"He recibido los siguientes documentos: {filenames}.\n\n"
                "Indícame qué análisis jurídico deseas realizar con ellos."
            )

        response = self.chat.invoke([HumanMessage(content=prompt)])
        return response.content.strip()


# # -----------------------------------------------------------------------------
# # region            IMPORTACIONES
# # -----------------------------------------------------------------------------
# import re
# import json
# import asyncio
# from typing import Optional, List
# from fastapi import UploadFile
# from dotenv import load_dotenv, find_dotenv
# from app.config import settings
# from langchain_openai import AzureChatOpenAI
# from langchain.schema import HumanMessage
# from helpers.principal_function import _process_chat
# #endregion

# # -----------------------------------------------------------------------------
# # region           FUNCION EXTRACCION DE VARIABLES
# # -----------------------------------------------------------------------------
# load_dotenv(find_dotenv(), override=True)
# #endregion


# # -----------------------------------------------------------------------------
# # region            CLASE: TOOLS
# # -----------------------------------------------------------------------------
# class Tools:
#     def __init__(self):
#         self.chat = AzureChatOpenAI(
#             api_key=settings.AZURE_OPENAI_KEY,
#             azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
#             api_version=settings.AZURE_OPENAI_OPENAI_VERSION,
#             deployment_name=settings.AZURE_OPENAI_CHAT_DEPLOYMENT,
#             temperature=0.7,
#         )

#         self._session_id: Optional[str] = None
#         self._user_id: Optional[str] = None
#         self._files: Optional[List[UploadFile]] = None


# # -----------------------------------------------------------------------------
# #                   Funciones de decision
# # -----------------------------------------------------------------------------
#     def bind_context(
#         self,
#         session_id: Optional[str],
#         user_id: Optional[str],
#         files: Optional[List[UploadFile]],
#     ) -> None:
#         self._session_id = session_id
#         self._user_id = user_id
#         self._files = files

#     def _extract_last_user_question(self, text: str) -> str:
#         if not text:
#             return ""
#         m = re.search(r"<usuario>:\s*(.*?)\n<asistente>:\s*$", text, flags=re.DOTALL | re.IGNORECASE)
#         if m:
#             return (m.group(1) or "").strip()
#         return text.strip()

#     def _decide_mode(self, question: str) -> str:
#         """
#         Regla simple (rápida):
#         - Si el usuario pide explícitamente generar el documento/providencia -> providencia
#         - Si no -> answer
#         Luego si quieres lo hacemos con LLM sin 'palabras quemadas'.
#         """
#         q = (question or "").lower()

#         keywords_providencia = [
#             "providencia",
#             "generar documento",
#             "genera el documento",
#             "crear documento",
#             "descargar",
#             "docx",
#             "word",
#         ]

#         if any(k in q for k in keywords_providencia):
#             return "providencia"

#         # Si subió archivos, por defecto responde (no genera doc a menos que lo pida)
#         return "answer"

# # -----------------------------------------------------------------------------
# # region            TOOL:RAG
# # -----------------------------------------------------------------------------
#     def tool_rag(self, query: str) -> str:
#         question = self._extract_last_user_question(query)
#         if not self._session_id or not self._user_id:
#             return "No se pudo identificar la sesión o el usuario. Intenta nuevamente."
#         mode = self._decide_mode(question)
#         result = asyncio.run(
#             _process_chat(
#                 question=question,
#                 files=self._files,
#                 session_id=self._session_id,
#                 user_id=self._user_id,
#                 mode=mode, 
#             )
#         )
#         answer = result.get("answer")
#         if isinstance(answer, dict):
#             return json.dumps(answer, ensure_ascii=False, indent=2)
#         return str(answer or "")

# # -----------------------------------------------------------------------------
# # region            TOOL:CONVERSACIONAL
# # -----------------------------------------------------------------------------
#     def tool_conversacional(self, prompt: str) -> str:
#         if self._files:
#             filenames = ", ".join([f.filename for f in self._files if f.filename])
#             return (
#                 f"Veo que adjuntaste: {filenames}.\n\n"
#                 "¿Qué quieres hacer con esos documentos o escríbeme qué necesitas)."
#             )
#         response = self.chat.invoke([HumanMessage(content=prompt)])
#         return response.content
