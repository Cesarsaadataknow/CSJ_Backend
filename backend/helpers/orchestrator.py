
import uuid
import asyncio
from typing import Optional, List
from fastapi import UploadFile, HTTPException
from dotenv import load_dotenv, find_dotenv
from langchain_openai import AzureChatOpenAI
from langchain.agents import initialize_agent, Tool
from langchain.agents.agent_types import AgentType
from app.config import settings
from helpers.tools import Tools
from core.ai_services import AIServices
from helpers.prompts import system_prompt_agente
from helpers.read_service import DocumentIntelligenceExtractor, TextCleaner
from helpers.indexacion import AzureSearchIndexer, FabricSearchIndexer, Chunker
from helpers.ingestion import IngestionService
from core.rag_service import RAGFabricService, RAGService
from helpers.indexacion import EmbeddingService  
from utils.functions import Functions

load_dotenv(find_dotenv(), override=True)

MAX_CONVERSATIONS_PER_USER = 10
MAX_FILES_PER_SESSION = 40
ALLOWED_CT = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}

class Orchestrator:
    def __init__(self):
        # 1) Ingesta userdocs (lo tuyo)
        self.search_manager = AzureSearchIndexer()  
        self.extractor = DocumentIntelligenceExtractor()
        self.cleaner = TextCleaner()
        self.chunker = Chunker(max_tokens=900, overlap=150)
        self.embedder = EmbeddingService()
        # 2) Cerebro
        self.llm = AzureChatOpenAI(
            api_key=settings.AZURE_OPENAI_KEY,
            azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
            api_version=settings.AZURE_OPENAI_OPENAI_VERSION,
            deployment_name=settings.AZURE_OPENAI_CHAT_DEPLOYMENT,
            temperature=0.4,
        )

        self.function = Functions()

        # 3) DB
        self.cosmosdb = AIServices.AzureCosmosDB()


        # 4.2 Indexer corpus (solo consulta, no ingesta)
        self.corpus_indexer = FabricSearchIndexer()

        # 4.3 RAG corpus
        self.rag_corpus = RAGFabricService(embedder=self.embedder, indexer=self.corpus_indexer)
        self.rag_userdocs = RAGService(embedder=self.embedder, indexer=self.search_manager)

        self.ingestor = IngestionService(
            extractor=self.extractor,
            cleaner=self.cleaner,
            chunker=self.chunker,
            embedder=self.embedder,
            indexer=self.search_manager,
        )

        self.tools_class = Tools(
            rag_userdocs=self.rag_userdocs,   # tu RAGService de docs subidos
            rag_corpus=self.rag_corpus,       # tu servicio del índice del compa (FabricSearchIndexer)
            llm_chat=self.llm,                # tu AzureChatOpenAI
        )


        # --- DEFINICIÓN DE HERRAMIENTAS ---
        self.tools = [
            Tool.from_function(
                func=self.tools_class.tool_rag_userdocs,
                name="tool_rag_userdocs",
                description=(
                    "Usa esta herramienta cuando la pregunta sea sobre documentos SUBIDOS por el usuario "
                    "en la sesión actual. Ej: 'este documento', 'lo que subí', 'adjunto', "
                    "'resume el archivo', 'qué dice el documento sobre...'."
                ),
            ),
            Tool.from_function(
                func=self.tools_class.tool_rag_fabric,
                name="tool_rag_corpus",
                description=(
                    "Usa esta herramienta cuando la pregunta sea sobre el CORPUS/JURISPRUDENCIA "
                    "(índice del compa). Ej: 'CSJ', 'jurisprudencia', 'sentencia', 'radicado', "
                    "'actor demandado', 'problema jurídico'."
                ),
            ),
            Tool.from_function(
                func=self.tools_class.tool_conversacional,
                name="tool_conversacional",
                description="Usa esta herramienta para saludos, despedidas o charla que NO requiera consultar índices."
            ),
            # Tool.from_function(
            #     func=self.tools_class.tool_word,
            #     name="tool_generar_word",
            #     description=(
            #         "Usa esta herramienta ÚNICAMENTE cuando el usuario pida descargar/crear/generar/exportar "
            #         "un archivo Word."
            #     )
            # ),
        ]

        # 6) Agente
        self.agent = initialize_agent(
            tools=self.tools,
            llm=self.llm,
            agent=AgentType.OPENAI_FUNCTIONS,
            verbose=True,
            handle_parsing_errors=True,
            agent_kwargs={"system_message": system_prompt_agente},
        )


    # -------------------------------------------------------------------------
    # MÉTODO PRINCIPAL (ASYNC)
    # -------------------------------------------------------------------------
    async def ejecutar_agente(
        self,
        mensaje_usuario: str,
        user_id: str,
        session_id: Optional[str] = None,
        files: Optional[List[UploadFile]] = None,
    ) -> dict:

        # ------------------------------------------------------------
        # 1) Validación usuario
        # ------------------------------------------------------------
        if not user_id:
            raise HTTPException(status_code=401, detail="Usuario no autenticado.")

        # ------------------------------------------------------------
        # 2) Sesión nueva + límite 10 conversaciones
        # ------------------------------------------------------------
        if not session_id:
            user_sessions = self.cosmosdb.get_user_sessions(user_id)
            if len(user_sessions) >= MAX_CONVERSATIONS_PER_USER:
                raise HTTPException(
                    status_code=409,
                    detail=f"Límite alcanzado: máximo {MAX_CONVERSATIONS_PER_USER} conversaciones por usuario."
                )
            session_id = str(uuid.uuid4())

        files = files or []
        files_uploaded_now = len(files) > 0

        # ------------------------------------------------------------
        # 3) Validación límite 40 archivos por sesión
        # ------------------------------------------------------------
        if files_uploaded_now:
            existing_files = self.cosmosdb.count_uploaded_files(session_id)
            if existing_files + len(files) > MAX_FILES_PER_SESSION:
                raise HTTPException(
                    status_code=409,
                    detail=f"Límite de archivos alcanzado ({MAX_FILES_PER_SESSION} máx). Ya tienes {existing_files}."
                )

        # ------------------------------------------------------------
        # 4) Detectar si es solo subida (sin pregunta real)
        # ------------------------------------------------------------
        only_upload = False
        if files_uploaded_now:
            if self.function.key_words(mensaje_usuario):
                only_upload = True
            else:
                # Zona gris: si el mensaje es corto o ambiguo, que decida el LLM
                t = (mensaje_usuario or "").strip()
                if len(t) < 40 and "?" not in t:
                    only_upload = await self.function.llm_detect(t,self.llm)

        # ------------------------------------------------------------
        # 5) Ingesta: usar TU servicio (extract -> chunk -> embed -> upload)
        # ------------------------------------------------------------
        if files_uploaded_now:
            for f in files:
                ct = (f.content_type or "").lower()
                name = f.filename or "archivo"

                if ct not in ALLOWED_CT:
                    raise HTTPException(status_code=400, detail=f"Tipo no permitido: {name} ({ct})")

                file_bytes = await f.read()

                # Esto es lo que tú ya tenías funcionando:
                # ingestor.ingest(...) crea docs y llama indexer.upload(...)
                try:
                    await asyncio.to_thread(
                        self.ingestor.ingest,
                        file_bytes,
                        ct,
                        name,
                        user_id,
                        session_id
                    )
                finally:
                    try:
                        await f.seek(0)
                    except Exception:
                        pass

        # ------------------------------------------------------------
        # 6) Bind contexto a Tools (para userdocs por session_id/user_id)
        # ------------------------------------------------------------
        self.tools_class.bind_context(session_id=session_id, user_id=user_id, files=files)

        # ------------------------------------------------------------
        # 7) Caso: subió archivos sin pregunta -> GPT pregunta “qué hacer”
        # ------------------------------------------------------------
        if only_upload:
            nombres = ", ".join([f.filename for f in files if f.filename]) or "tus archivos"
            output = (
                f"Recibí: {nombres}.\n\n"
                "¿Qué quieres hacer con estos documentos?\n"
                "1) Resumir\n"
                "2) Buscar algo específico\n"
                "3) Extraer información clave\n"
                "4) Comparar documentos\n"
                "5) Generar un Word con un informe\n"
            )

            self.cosmosdb.save_message_chat(
                session_id=session_id,
                user_id=user_id,
                user_question=mensaje_usuario or "(subida de archivos)",
                ia_response=output,
                channel="web",
                extra={"mode": "only_upload"},
            )

            return {"reply_text": output, "session_id": session_id}

        # ------------------------------------------------------------
        # 8) Memoria: recuperar historial de Cosmos
        # ------------------------------------------------------------
        historial = self.cosmosdb.get_session_messages(session_id) or []

        # recorta para no explotar tokens
        historial = historial[-20:]

        contexto_chat = ""
        for m in historial:
            contexto_chat += f"<usuario>: {m.get('UserQuestion','')}\n"
            contexto_chat += f"<asistente>: {m.get('IAResponse','')}\n"

        # ------------------------------------------------------------
        # 9) Instrucción sistema para enrutar tools
        # ------------------------------------------------------------
        if files_uploaded_now:
            nombres = ", ".join([f.filename for f in files if f.filename])
            instruccion_sistema = (
                f"SISTEMA: El usuario subió archivos: {nombres}. Ya están indexados.\n"
                "- Si la pregunta es sobre documentos subidos -> tool_rag_userdocs\n"
                "- Si es sobre el índice del compa (corpus/jurisprudencia) -> tool_rag_corpus\n"
                "- Si pide descargar/generar -> tool_generar_word\n"
                "- Si es charla -> tool_conversacional\n"
            )
        else:
            instruccion_sistema = (
                "SISTEMA: No hay archivos nuevos.\n"
                "- Si la pregunta es sobre documentos subidos -> tool_rag_userdocs\n"
                "- Si es sobre el índice del compa (corpus/jurisprudencia) -> tool_rag_corpus\n"
                "- Si pide descargar/generar -> tool_generar_word\n"
                "- Si es charla -> tool_conversacional\n"
            )

        input_modelo = f"""
Historial:
{contexto_chat}

{instruccion_sistema}

<usuario>: {mensaje_usuario}
<asistente>:
"""

        # ------------------------------------------------------------
        # 10) Ejecutar agente
        # ------------------------------------------------------------
        respuesta = await asyncio.to_thread(self.agent.invoke, {"input": input_modelo})
        output = (respuesta.get("output") or "").strip()

        # ------------------------------------------------------------
        # 11) Guardar en Cosmos
        # ------------------------------------------------------------
        self.cosmosdb.save_message_chat(
            session_id=session_id,
            user_id=user_id,
            user_question=mensaje_usuario,
            ia_response=output,
            channel="web",
            extra={"tools": str(respuesta.get("intermediate_steps"))},
        )

        return {"reply_text": output, "session_id": session_id}
