import json
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

# --- IMPORTAMOS TUS SERVICIOS ---
from helpers.read_service import DocumentParser 
from helpers.indexacion import SearchManager

load_dotenv(find_dotenv(), override=True)

# --- CONSTANTES DE NEGOCIO ---
MAX_CONVERSATIONS_PER_USER = 10
MAX_FILES_PER_SESSION = 40

class Orchestrator:
    def __init__(self):
        # 1. Instanciamos los motores de Ingesta (Lectura e Indexación)
        self.doc_parser = DocumentParser()
        self.search_manager = SearchManager()

        # 2. Configuración del Cerebro (LLM)
        self.llm = AzureChatOpenAI(
            api_key=settings.AZURE_OPENAI_KEY,
            azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
            api_version=settings.AZURE_OPENAI_OPENAI_VERSION,
            deployment_name=settings.AZURE_OPENAI_CHAT_DEPLOYMENT,
            temperature=0.4, # Temperatura baja para ser preciso en RAG
        )

        # 3. Configuración de Herramientas y Base de Datos
        # Le pasamos el search_manager a Tools para que pueda buscar
        self.tools_class = Tools(search_manager=self.search_manager) 
        self.cosmosdb = AIServices.AzureCosmosDB()

        # --- DEFINICIÓN DE HERRAMIENTAS INTELIGENTES ---
        self.tools = [
            # TOOL 1: RAG (Leer y Analizar)
            Tool.from_function(
                func=self.tools_class.tool_rag,
                name="tool_rag",
                description=(
                    "Usa esta herramienta SIEMPRE que necesites responder preguntas basadas "
                    "en el contenido de los documentos cargados, hacer resúmenes, "
                    "buscar cláusulas específicas o extraer datos del texto."
                ),
            ),
            # TOOL 2: Conversacional (Cordialidad)
            Tool.from_function(
                func=self.tools_class.tool_conversacional,
                name="tool_conversacional",
                description="Usa esta herramienta para saludos, despedidas o charlas que NO requieran leer el documento."
            ),
            # TOOL 3: Generar Word (Acción Final)
            Tool.from_function(
                func=self.tools_class.tool_generar_word,
                name="tool_generar_word",
                description=(
                    "Usa esta herramienta ÚNICAMENTE cuando el usuario pida explícitamente "
                    "descargar, crear, generar, exportar o 'pasame el archivo' en formato Word."
                )
            ),
        ]

        # 4. Inicialización del Agente
        self.agent = initialize_agent(
            tools=self.tools,
            llm=self.llm,
            agent=AgentType.OPENAI_FUNCTIONS, # El mejor modo para Azure OpenAI
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

        # ---------------------------------------------------------------------
        # 1. VALIDACIONES INICIALES (Seguridad y Límites)
        # ---------------------------------------------------------------------
        if not user_id:
            raise HTTPException(status_code=401, detail="Usuario no autenticado.")

        # Si es sesión nueva, validamos que no tenga demasiadas
        if not session_id:
            user_sessions = self.cosmosdb.get_user_sessions(user_id)
            if len(user_sessions) >= MAX_CONVERSATIONS_PER_USER:
                raise HTTPException(
                    status_code=409,
                    detail=f"Límite alcanzado: Tienes {len(user_sessions)} conversaciones. Elimina una antigua para continuar."
                )
            session_id = str(uuid.uuid4())

        # ---------------------------------------------------------------------
        # 2. PROCESAMIENTO DE ARCHIVOS (Ingesta RAG)
        # ---------------------------------------------------------------------
        if files:
            # Validar cantidad de archivos en la sesión
            existing_files = self.cosmosdb.count_uploaded_files(session_id)
            if existing_files + len(files) > MAX_FILES_PER_SESSION:
                 raise HTTPException(
                    status_code=409,
                    detail=f"Límite de archivos alcanzado ({MAX_FILES_PER_SESSION} máx). Ya tienes {existing_files}."
                )

            print(f"📂 [Ingesta] Procesando {len(files)} archivos para sesión {session_id}...")
            
            for file in files:
                try:
                    # A. Lectura Asíncrona (No bloquea el server)
                    content = await file.read()
                    filename = file.filename
                    
                    # B. Parseo (Azure Doc Intelligence) -> Hilo secundario
                    texto_markdown = await asyncio.to_thread(self.doc_parser.parse_file, content)
                    
                    if texto_markdown:
                        # C. Indexación (Azure AI Search) -> Hilo secundario
                        await asyncio.to_thread(
                            self.search_manager.index_content, 
                            texto_markdown, filename, session_id
                        )
                    else:
                        print(f"⚠️ Archivo vacío o ilegible: {filename}")

                except Exception as e:
                    print(f"❌ Error procesando {file.filename}: {e}")
                finally:
                    # Resetear puntero por seguridad
                    await file.seek(0)

        # ---------------------------------------------------------------------
        # 3. CONTEXTO Y PROMPT DINÁMICO
        # ---------------------------------------------------------------------
        # Vinculamos datos para que las Tools sepan en qué sesión buscar
        self.tools_class.bind_context(
            session_id=session_id,
            user_id=user_id,
            files=files
        )

        # Detectamos si ACABAN de subir archivos en este momento exacto
        nombres_archivos_nuevos = [f.filename for f in files] if files else []
        
        instruccion_sistema = ""
        if nombres_archivos_nuevos:
            # CASO A: Recepción de Archivos
            # Instrucción clara: CONFIRMAR y PREGUNTAR. No alucinar análisis todavía.
            instruccion_sistema = (
                f"SISTEMA: El usuario acaba de subir: {', '.join(nombres_archivos_nuevos)}. "
                "TU TAREA AHORA ES: 1. Confirmar que recibiste los archivos. "
                "2. Preguntar amablemente qué desea hacer con ellos (ej: ¿Resumir, Analizar, Extraer datos?). "
                "NO uses ninguna tool todavía."
            )
        else:
            # CASO B: Flujo Normal
            # Instrucción clara: Usar las herramientas según la intención.
            instruccion_sistema = (
                "SISTEMA: Tienes acceso a documentos. "
                "- Si preguntan contenido -> Usa 'tool_rag'. "
                "- Si piden generar el documento final -> Usa 'tool_generar_word'. "
                "- Si es charla normal -> Usa 'tool_conversacional'."
            )

        # Recuperamos historial para memoria
        historial = self.cosmosdb.get_session_messages(session_id)
        contexto_chat = "Historial:\n\n"
        for m in historial:
            contexto_chat += f"<usuario>: {m.get('UserQuestion','')}\n"
            contexto_chat += f"<asistente>: {m.get('IAResponse','')}\n"

        # Armamos el prompt final
        input_modelo = f"""
        {contexto_chat}

        {instruccion_sistema}

        <usuario>: {mensaje_usuario}
        <asistente>:
        """

        # ---------------------------------------------------------------------
        # 4. EJECUCIÓN DEL AGENTE
        # ---------------------------------------------------------------------
        # El agente decide inteligentemente qué hacer
        respuesta = await asyncio.to_thread(self.agent.invoke, {"input": input_modelo})
        output = respuesta.get("output", "").strip()

        # ---------------------------------------------------------------------
        # 5. GUARDAR Y RETORNAR
        # ---------------------------------------------------------------------
        self.cosmosdb.save_message_chat(
            session_id=session_id,
            user_id=user_id,
            user_question=mensaje_usuario,
            ia_response=output,
            channel="web",
            extra={"tools": str(respuesta.get("intermediate_steps"))},
        )

        # ¡OJO! Aquí ya NO hay validaciones manuales de "if documento return...".
        # Dejamos que el Agente y sus Tools manejen todo.
        
        return {
            "reply_text": output,
            "session_id": session_id,
        }