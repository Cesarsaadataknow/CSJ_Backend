# -----------------------------------------------------------------------------
# region            IMPORTACIONES
# -----------------------------------------------------------------------------
import json
import uuid
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
#endregion


# -----------------------------------------------------------------------------
# region           FUNCION EXTRACCION DE VARIABLES
# -----------------------------------------------------------------------------
load_dotenv(find_dotenv(), override=True)
#endregion


# -----------------------------------------------------------------------------
# region           VALORES PARA CONDICIONES (cONVERSACIONES Y DOCUMENTOS)
# -----------------------------------------------------------------------------
MAX_CONVERSATIONS_PER_USER = 10
MAX_FILES_PER_SESSION = 40
#endregion


# -----------------------------------------------------------------------------
# region           AGENTE:EJECUCION E HISTORIAL - CONTEXTO
# -----------------------------------------------------------------------------
class Orchestrator:
    def __init__(self):
        self.llm = AzureChatOpenAI(
            api_key=settings.AZURE_OPENAI_KEY,
            azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
            api_version=settings.AZURE_OPENAI_OPENAI_VERSION,
            deployment_name=settings.AZURE_OPENAI_CHAT_DEPLOYMENT,
            temperature=0.7,
        )

        # ----------------------------
        # Clases
        # ----------------------------
        self.tools_class = Tools()
        self.cosmosdb = AIServices.AzureCosmosDB()


        # ----------------------------
        # Tools
        # ----------------------------
        self.tools = [
            Tool.from_function(
                func=self.tools_class.tool_rag,
                name="tool_rag",
                description=(
                    "Usa esta tool para responder preguntas jurídicas basadas en los documentos "
                    "indexados y/o documentos cargados por el usuario (RAG)."
                ),
            ),
            Tool.from_function(
                func=self.tools_class.tool_conversacional,
                name="tool_conversacional",
                description=(
                    "Responde saludos o mensajes cortos de cortesía como 'hola', 'gracias', "
                    "'buenos días', 'cómo estás', etc. Si el usuario adjunta documentos y no pide "
                    "nada específico, guía preguntando qué desea hacer con ellos."
                ),
            ),
        ]

        system_prompt = system_prompt_agente

        self.agent = initialize_agent(
            tools=self.tools,
            llm=self.llm,
            agent=AgentType.OPENAI_FUNCTIONS,
            verbose=True,
            handle_parsing_errors=True,
            agent_kwargs={"system_message": system_prompt},
        )

    # ----------------------------
    # AGENTE
    # ----------------------------
    def ejecutar_agente(
        self,
        mensaje_usuario: str,
        user_id: str,
        session_id: Optional[str] = None,
        files: Optional[List[UploadFile]] = None,
    ) -> dict:

        # ----------------------------
        # Validación usuario
        # ----------------------------
        if not user_id:
            raise HTTPException(status_code=401, detail="Usuario no autenticado.")

        # ----------------------------
        # Límite 10 conversaciones
        # ----------------------------
        if not session_id:
            user_sessions = self.cosmosdb.get_user_sessions(user_id)
            if len(user_sessions) >= MAX_CONVERSATIONS_PER_USER:
                raise HTTPException(
                    status_code=409,
                    detail=(
                        f"Límite alcanzado: máximo {MAX_CONVERSATIONS_PER_USER} conversaciones por usuario. "
                        "Por favor elimina una conversacion del panel izquierdo para crear una nueva."
                    ),
                )
            session_id = str(uuid.uuid4())

        # ----------------------------
        # Límite 40 documentos por sesión
        # ----------------------------
        if files:
            existing_files = self.cosmosdb.count_uploaded_files(session_id)
            if existing_files + len(files) > MAX_FILES_PER_SESSION:
                raise HTTPException(
                    status_code=409,
                    detail=(
                        f"Límite alcanzado: máximo {MAX_FILES_PER_SESSION} documentos por sesión. "
                        f"Ya hay {existing_files} y estás intentando subir {len(files)}."
                    ),
                )
            
        # ----------------------------
        # Generacion de historial y contexto de agente
        # ----------------------------    

        self.tools_class.bind_context(session_id=session_id, user_id=user_id, files=files)
        historial = self.cosmosdb.get_session_messages(session_id)
        contexto = (
            "Historial de la sesión (usa esto para mantener continuidad):\n\n"
        )
        for mensaje in historial:
            uq = (mensaje.get("UserQuestion") or "").strip()
            ar = mensaje.get("IAResponse")
            if isinstance(ar, dict):
                ar = json.dumps(ar, ensure_ascii=False)  
            ar = (ar or "").strip()
            contexto += f"<usuario>: {uq}\n<asistente>: {ar}\n"
        input_modelo = f"{contexto}<usuario>: {mensaje_usuario}\n<asistente>:"

        # ----------------------------
        # Ejecucion de agente
        # ----------------------------    

        respuesta = self.agent.invoke({"input": input_modelo})
        output = (respuesta.get("output") or "").replace("**", "").strip()
        self.cosmosdb.save_message_chat(
            session_id=session_id,
            user_id=user_id,
            user_question=mensaje_usuario,
            ia_response=output,
            channel="web",
            extra={"tool_used": str(respuesta.get("intermediate_steps", ""))},
        )

        return {"reply_text": output, "session_id": session_id}
# endregion