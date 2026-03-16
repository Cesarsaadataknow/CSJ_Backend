# -----------------------------------------------------------------------------
# region           IMPORTACIONES
# -----------------------------------------------------------------------------
import uuid
import asyncio
import json
from pathlib import Path
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
from helpers.document_generator import DocxTemplateBuilder, DocumentGeneratorService
from helpers.ingestion import IngestionService
from core.rag_service import RAGFabricService, RAGService
from helpers.indexacion import EmbeddingService
from utils.functions import Functions

load_dotenv(find_dotenv(), override=True)
# endregion

# -----------------------------------------------------------------------------
# region           VARIABLES DE CONDICION
# -----------------------------------------------------------------------------
MAX_CONVERSATIONS_PER_USER = 10
MAX_FILES_PER_SESSION = 40
ALLOWED_CT = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}
# endregion

# -----------------------------------------------------------------------------
# region           RUTA DE TEMPLATE
# -----------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
template_path = (BASE_DIR.parent / "templates" / "Documento_Consejo_Estado_template.docx").resolve()
# endregion


# -----------------------------------------------------------------------------
# region           CLASE ORQUESTADOR
# -----------------------------------------------------------------------------
class Orchestrator:
    # ------------------------------------------------------------
    # 1) Inicialización
    # ------------------------------------------------------------
    def __init__(self):
        self.llm = AzureChatOpenAI(
            api_key=settings.AZURE_OPENAI_KEY,
            azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
            api_version=settings.AZURE_OPENAI_OPENAI_VERSION,
            deployment_name=settings.AZURE_OPENAI_CHAT_DEPLOYMENT,
            temperature=0.4,
        )
        self.extractor = DocumentIntelligenceExtractor()
        self.cleaner = TextCleaner()
        self.chunker = Chunker(max_tokens=900, overlap=150)
        self.embedder = EmbeddingService()
        self.function = Functions()
        self.cosmosdb = AIServices.AzureCosmosDB()
        self.corpus_indexer = FabricSearchIndexer()
        self.search_manager = AzureSearchIndexer()

        self.rag_corpus = RAGFabricService(
            embedder=self.embedder,
            indexer=self.corpus_indexer
        )
        self.rag_userdocs = RAGService(
            embedder=self.embedder,
            indexer=self.search_manager
        )

        self.doc = DocxTemplateBuilder(str(template_path))
        self.doc_generator = DocumentGeneratorService(
            llm_chat=self.llm,
            embedder=self.embedder,
            indexer_userdocs=self.search_manager,
            indexer_corpus=self.corpus_indexer,
            docx_builder=self.doc,
        )

        self.ingestor = IngestionService(
            extractor=self.extractor,
            cleaner=self.cleaner,
            chunker=self.chunker,
            embedder=self.embedder,
            indexer=self.search_manager,
        )

        self.tools_class = Tools(
            rag_userdocs=self.rag_userdocs,
            rag_corpus=self.rag_corpus,
            llm_chat=self.llm,
            doc_generator=self.doc_generator,
            cosmosdb=self.cosmosdb,
        )

        # ------------------------------------------------------------
        # 2) Tools
        # ------------------------------------------------------------
        self.tools = [
            Tool.from_function(
                func=self.tools_class.tool_rag_userdocs,
                name="tool_rag_userdocs",
                description=(
                    "Usa esta herramienta cuando la pregunta sea sobre documentos SUBIDOS "
                    "por el usuario en la sesión actual."
                ),
            ),
            Tool.from_function(
                func=self.tools_class.tool_rag_fabric,
                name="tool_rag_corpus",
                description=(
                    "Usa esta herramienta cuando la pregunta sea sobre el CORPUS/JURISPRUDENCIA."
                ),
            ),
            Tool.from_function(
                func=self.tools_class.tool_conversacional,
                name="tool_conversacional",
                description="Usa esta herramienta para charla general."
            ),
            Tool.from_function(
                func=self.tools_class.tool_word,
                name="tool_generar_word",
                description="Usa esta herramienta SOLO para generar Word.",
                return_direct=True,
            ),
        ]

        # ------------------------------------------------------------
        # 3) Agente
        # ------------------------------------------------------------
        self.agent = initialize_agent(
            tools=self.tools,
            llm=self.llm,
            agent=AgentType.OPENAI_FUNCTIONS,
            verbose=True,
            handle_parsing_errors=True,
            agent_kwargs={"system_message": system_prompt_agente},
        )
# endregion


# -----------------------------------------------------------------------------
# region           MÉTODO PRINCIPAL
# -----------------------------------------------------------------------------
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
        # 2) Sesión
        # ------------------------------------------------------------
        if not session_id:
            sesiones = self.cosmosdb.get_user_sessions(user_id)
            if len(sesiones) >= MAX_CONVERSATIONS_PER_USER:
                raise HTTPException(status_code=409, detail="Límite de sesiones alcanzado.")
            session_id = str(uuid.uuid4())

        files = files or []
        files_uploaded_now = len(files) > 0

        # ------------------------------------------------------------
        # 3) Límite archivos
        # ------------------------------------------------------------
        if files_uploaded_now:
            existentes = self.cosmosdb.count_uploaded_files(session_id)
            if existentes + len(files) > MAX_FILES_PER_SESSION:
                raise HTTPException(status_code=409, detail="Límite de archivos alcanzado.")

        # ------------------------------------------------------------
        # 4) Detectar solo subida
        # ------------------------------------------------------------
        only_upload = False
        if files_uploaded_now:
            if self.function.key_words(mensaje_usuario):
                only_upload = True
            else:
                t = (mensaje_usuario or "").strip()
                if len(t) < 40 and "?" not in t:
                    only_upload = await self.function.llm_detect(t, self.llm)

        # ------------------------------------------------------------
        # 5) Ingesta
        # ------------------------------------------------------------
        uploaded_batch = []

        if files_uploaded_now:
            registry = self.cosmosdb.get_uploaded_files_registry(session_id)
            current_total = len(registry)

            for idx, f in enumerate(files, start=1):
                ct = (f.content_type or "").lower()
                if ct not in ALLOWED_CT:
                    raise HTTPException(status_code=400, detail=f"Tipo no permitido: {f.filename}")

                data = await f.read()

                result = await asyncio.to_thread(
                    self.ingestor.ingest,
                    data,
                    ct,
                    f.filename,
                    user_id,
                    session_id,
                )

                if result and result.get("file_id"):
                    uploaded_batch.append(
                        {
                            "file_id": result["file_id"],
                            "file_name": result["file_name"],
                            "position_in_batch": idx,
                            "global_position": current_total + idx,
                        }
                    )

            if uploaded_batch:
                self.cosmosdb.save_uploaded_batch(
                    session_id=session_id,
                    user_id=user_id,
                    uploaded_files=uploaded_batch,
                    channel="web",
                )

        # ------------------------------------------------------------
        # 6) Bind contexto
        # ------------------------------------------------------------
        self.tools_class.bind_context(session_id=session_id, user_id=user_id, files=files)

        # ------------------------------------------------------------
        # 7) Solo subida
        # ------------------------------------------------------------
        if only_upload:
            output = "Archivos recibidos. ¿Qué deseas hacer con ellos?"
            self.cosmosdb.save_message_chat(
                session_id=session_id,
                user_id=user_id,
                user_question=mensaje_usuario,
                ia_response=output,
                channel="web",
                extra={
                    "mode": "only_upload",
                    "uploaded_files": uploaded_batch,
                },
            )
            return {"reply_text": output, "session_id": session_id}

        # ------------------------------------------------------------
        # 8) Historial
        # ------------------------------------------------------------
        historial = self.cosmosdb.get_session_messages(session_id)[-20:]
        contexto_chat = ""
        for m in historial:
            contexto_chat += f"<usuario>: {m.get('UserQuestion','')}\n"
            contexto_chat += f"<asistente>: {m.get('IAResponse','')}\n"

        # ------------------------------------------------------------
        # 9) Instrucción sistema
        # ------------------------------------------------------------
        instruccion_sistema = (
            "SISTEMA:\n"
            "- Documentos subidos -> tool_rag_userdocs\n"
            "- Corpus jurídico -> tool_rag_corpus\n"
            "- Word -> tool_generar_word\n"
            "- Charla -> tool_conversacional\n"
        )

        # >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
        # >>> AJUSTE FABRIC: PRECONSULTA CUANDO NO HAY ARCHIVOS <<<
        # >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
        contexto_fabric = ""
        if not files_uploaded_now:
            try:
                resultado = self.rag_corpus.query(
                    question=mensaje_usuario,
                    top_k=5
                )
                if isinstance(resultado, str):
                    contexto_fabric = resultado
                elif isinstance(resultado, list):
                    contexto_fabric = "\n".join(
                        [r.get("content", "") for r in resultado]
                    )
            except Exception:
                contexto_fabric = ""
        # >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>

        input_modelo = f"""
Historial:
{contexto_chat}

{instruccion_sistema}

CONTEXTO JURÍDICO DEL CORPUS (Fabric):
{contexto_fabric if contexto_fabric else "Sin contexto adicional."}

<usuario>: {mensaje_usuario}
<asistente>:
"""

        # ------------------------------------------------------------
        # 10) Ejecutar agente
        # ------------------------------------------------------------
        respuesta = await asyncio.to_thread(
            self.agent.invoke,
            {"input": input_modelo}
        )

        raw_output = respuesta.get("output")
        output = raw_output if isinstance(raw_output, str) else json.dumps(raw_output, ensure_ascii=False)

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

# endregion

