# -----------------------------------------------------------------------------
# region            IMPORTACIONES
# -----------------------------------------------------------------------------
import re
import json
from typing import Optional, List
from fastapi import UploadFile
from dotenv import load_dotenv, find_dotenv
from app.config import settings
from langchain_openai import AzureChatOpenAI
from langchain.schema import HumanMessage
from helpers.indexacion import SearchManager 
# endregion

# -----------------------------------------------------------------------------
# region           FUNCION EXTRACCION DE VARIABLES
# -----------------------------------------------------------------------------
load_dotenv(find_dotenv(), override=True)
# endregion


# -----------------------------------------------------------------------------
# region            CLASE: TOOLS
# -----------------------------------------------------------------------------
class Tools:
    # Aceptamos search_manager en el init
    def __init__(self, search_manager: Optional[SearchManager] = None):
        self.chat = AzureChatOpenAI(
            api_key=settings.AZURE_OPENAI_KEY,
            azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
            api_version=settings.AZURE_OPENAI_OPENAI_VERSION,
            deployment_name=settings.AZURE_OPENAI_CHAT_DEPLOYMENT,
            temperature=0.7,
        )

        # Si no nos pasan el manager, intentamos instanciarlo (aunque mejor que venga del orquestador)
        self.search_manager = search_manager if search_manager else SearchManager()

        self._session_id: Optional[str] = None
        self._user_id: Optional[str] = None
        self._files: Optional[List[UploadFile]] = None


# -----------------------------------------------------------------------------
#                   Funciones de decision
# -----------------------------------------------------------------------------
    def bind_context(
        self,
        session_id: Optional[str],
        user_id: Optional[str],
        files: Optional[List[UploadFile]],
    ):
        self._session_id = session_id
        self._user_id = user_id
        self._files = files

    def _extract_last_user_question(self, text: str) -> str:
        if not text:
            return ""
<<<<<<< HEAD
        m = re.search(
            r"<usuario>:\s*(.*?)\n<asistente>:\s*$",
            text,
            flags=re.DOTALL | re.IGNORECASE,
        )
        return (m.group(1) if m else text).strip()

    def _decide_mode(self, question: str) -> str:
        q = (question or "").lower()
        if any(
            k in q
            for k in [
                "generar documento",
                "descargar documento",
                "generar word",
                "providencia",
            ]
        ):
            return "providencia"
        return "answer"

    # ------------------------------------------------------------------
    # TOOL RAG (CLAVE)
    # ------------------------------------------------------------------
=======
        # Extrae lo último que dijo el usuario del historial que le pasa LangChain
        m = re.search(r"<usuario>:\s*(.*?)\n<asistente>:\s*$", text, flags=re.DOTALL | re.IGNORECASE)
        if m:
            return (m.group(1) or "").strip()
        
        # Si no encuentra el patrón, intenta limpiar un poco
        clean_text = text.replace("Contexto:", "").replace("Historial de la sesión:", "").strip()
        # Si es muy largo, cortamos para no enviar todo el historial como query
        return clean_text[-500:] if len(clean_text) > 500 else clean_text

# -----------------------------------------------------------------------------
# region            TOOL:RAG (ACTUALIZADA)
# -----------------------------------------------------------------------------
>>>>>>> ddf35c7 (Se realiza reconfiguracion del proceso de indexacion)
    def tool_rag(self, query: str) -> str:
        """
        Busca en los documentos indexados en Azure Search usando el session_id.
        """
        question = self._extract_last_user_question(query)
        
        if not self._session_id:
            return "Error técnico: No se identificó la sesión para buscar documentos."

        print(f"🔍 [Tool RAG] Buscando: '{question}' en sesión: {self._session_id}")

<<<<<<< HEAD
        result = asyncio.run(
            _process_chat(
                question=question,
                files=self._files,
                session_id=self._session_id,
                user_id=self._user_id,
                mode=mode,
=======
        try:
            # 1. Usar SearchManager para buscar en Azure AI Search
            # Esto filtra por session_id, asegurando que solo veas los docs de esta sesión
            docs = self.search_manager.search_similar(
                query=question, 
                session_id=self._session_id,
                top_k=5 # Traemos los 5 mejores fragmentos
>>>>>>> ddf35c7 (Se realiza reconfiguracion del proceso de indexacion)
            )
        )

            if not docs:
                return "No encontré información relevante en los documentos cargados para responder esa pregunta."

            # 2. Formatear los resultados para que el LLM los lea
            # Construimos un string claro con Fuente y Contenido
            context_result = "Información encontrada en los documentos:\n\n"
            for i, doc in enumerate(docs, 1):
                nombre_archivo = doc.get('source_file', 'Desconocido')
                contenido = doc.get('content', '').strip()
                context_result += f"--- Fragmento {i} (Fuente: {nombre_archivo}) ---\n{contenido}\n\n"

<<<<<<< HEAD
        return answer or ""
=======
            return context_result
>>>>>>> ddf35c7 (Se realiza reconfiguracion del proceso de indexacion)

        except Exception as e:
            print(f"❌ Error en tool_rag: {str(e)}")
            return f"Ocurrió un error al buscar en los documentos: {str(e)}"

# -----------------------------------------------------------------------------
# region            TOOL:CONVERSACIONAL
# -----------------------------------------------------------------------------
    def tool_conversacional(self, prompt: str) -> str:
        # Si hay archivos, sugerimos que pregunten sobre ellos
        if self._files:
            filenames = ", ".join([f.filename for f in self._files if f.filename])
            return (
<<<<<<< HEAD
                f"He recibido los documentos: {filenames}.\n\n"
                "Indícame qué análisis jurídico deseas realizar."
=======
                f"He recibido los archivos: {filenames}. "
                "Puedes preguntarme sobre su contenido, pedirme un resumen o que extraiga datos específicos."
>>>>>>> ddf35c7 (Se realiza reconfiguracion del proceso de indexacion)
            )
        
        # Si no hay archivos, charla normal
        response = self.chat.invoke([HumanMessage(content=prompt)])
        return response.content
    

    # En helpers/tools.py

<<<<<<< HEAD

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
=======
    def tool_generar_word(self, query: str) -> str:
        """
        Genera el documento final cuando el usuario lo pide explícitamente.
        """
        # Aquí puedes llamar a tu lógica de generación real o simplemente
        # devolver un mensaje clave para que el frontend muestre el botón.
        
        # Opción A: Devolver texto para que el agente responda
        return (
            "SISTEMA: Documento generado exitosamente. "
            "Dile al usuario que el archivo Word está listo para descargar."
        )
>>>>>>> ddf35c7 (Se realiza reconfiguracion del proceso de indexacion)
