import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List
from app.config import settings
from openai import AzureOpenAI
from langchain_openai import AzureChatOpenAI
from azure.cosmos import CosmosClient, PartitionKey, exceptions
from helpers.prompts import generate_session_title

class AIServices:

    @staticmethod
    def chat_client():
        return AzureOpenAI(
            api_key=settings.AZURE_OPENAI_KEY,
            azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
            api_version="2024-12-01-preview",  
            timeout=30                         
        )
    
    @staticmethod
    def _utc_iso() -> str:
        return datetime.now(timezone.utc).isoformat()
    
    
    class AzureCosmosDB:
        """
        Manejo de Cosmos DB con:
        - DB auto-creación
        - Containers auto-creación
        * sessions: PK /id
        * messages: PK /id_session
        """
        
        def __init__(self):
            self.endpoint = settings.AZURE_COSMOSDB_ENDPOINT
            self.key = settings.AZURE_COSMOSDB_KEY
            self.database_name = settings.AZURE_COSMOSDB_NAME
            self.container_sessions_name = settings.AZURE_COSMOSDB_CONTAINER_NAME_SESSION
            self.container_messages_name = settings.AZURE_COSMOSDB_CONTAINER_NAME_MGS

            self.openaikey= settings.AZURE_OPENAI_KEY
            self.endpointopenai=settings.AZURE_OPENAI_ENDPOINT
            self.modelo_ia = settings.AZURE_OPENAI_CHAT_DEPLOYMENT
            self.version_api_ia = settings.AZURE_OPENAI_OPENAI_VERSION
            
            self.llm = AzureChatOpenAI(
                azure_deployment=self.modelo_ia,
                api_version=self.version_api_ia,
                azure_endpoint=self.endpointopenai,
                api_key= self.openaikey,
                temperature=0.2,
            )

            if not self.endpoint or not self.key:
                raise ValueError("Faltan AZURE_COSMOS_DB_ENDPOINT o AZURE_COSMOS_DB_KEY en variables de entorno.")

            try:
                self.client = CosmosClient(self.endpoint, credential=self.key)

                # Crear DB si no existe
                self.database = self.client.create_database_if_not_exists(id=self.database_name)

                # Crear contenedores si no existen
                self.sessions_container = self.database.create_container_if_not_exists(
                    id=self.container_sessions_name,
                    partition_key=PartitionKey(path="/id"),
                )

                self.messages_container = self.database.create_container_if_not_exists(
                    id=self.container_messages_name,
                    partition_key=PartitionKey(path="/id_session"),
                )

                logging.info("Conectado a Cosmos DB y contenedores listos.")

            except exceptions.CosmosHttpResponseError as e:
                logging.error(f"Error de conexión a Cosmos DB: {str(e)}")
                raise

        # =========================
        # SESSIONS
        # =========================
        def session_exists(self, session_id: str) -> bool:
            try:
                self.sessions_container.read_item(item=session_id, partition_key=session_id)
                return True
            except exceptions.CosmosResourceNotFoundError:
                return False

        def create_session(self, session_data: Dict[str, Any]) -> Dict[str, Any]:
            """
            session_data esperado:
            {
            "session_id": "...",
            "user_id": "...",
            "session_name": "...",
            "channel": "web" | "api" | ...
            }
            """
            doc = {
                "id": session_data["session_id"],          
                "_id": session_data["session_id"],         
                "user_id": session_data.get("user_id"),
                "modelo_ia": self.modelo_ia,
                "version_api_ia": self.version_api_ia,
                "message": [],                            
                "fecha_creacion": AIServices._utc_iso(),
                "updated_at": AIServices._utc_iso(),
                "name_session": session_data.get("session_name", "Sesión"),
                "channel": session_data.get("channel", "web"),
            }
            return self.sessions_container.create_item(doc)

        def upsert_session(self, session_data: Dict[str, Any]) -> Dict[str, Any]:
            """
            Crea o actualiza (si ya existe).
            """
            doc = {
                "id": session_data["session_id"],
                "_id": session_data["session_id"],
                "user_id": session_data.get("user_id"),
                "modelo_ia": self.modelo_ia,
                "version_api_ia": self.version_api_ia,
                "message": session_data.get("message", []),
                "fecha_creacion": session_data.get("fecha_creacion", AIServices._utc_iso()),
                "updated_at": AIServices._utc_iso(),
                "name_session": session_data.get("session_name", "Sesión"),
                "channel": session_data.get("channel", "web"),
            }
            return self.sessions_container.upsert_item(doc)

        def touch_session(self, session_id: str):
            """
            Actualiza updated_at sin tocar lo demás (si existe).
            """
            try:
                session = self.sessions_container.read_item(item=session_id, partition_key=session_id)
                session["updated_at"] = AIServices._utc_iso()
                self.sessions_container.replace_item(item=session_id, body=session)
            except exceptions.CosmosResourceNotFoundError:
                pass

        # =========================
        # MESSAGES
        # =========================
        def save_message(self, message_data: Dict[str, Any]) -> Dict[str, Any]:
            doc_message = {
                "id": message_data["message_id"],

                # PK real del container messages
                "id_session": message_data["session_id"],

                # Campos principales
                "UserQuestion": message_data.get("user_question", ""),
                "IAResponse": message_data.get("ai_response", ""),

                # Extras opcionales
                "citations": message_data.get("citations", []),
                "file_path": message_data.get("file_path"),
                "extra": message_data.get("extra", {}),

                # Métricas
                "TokenIn": message_data.get("tokens_in", 0),
                "TokenOut": message_data.get("tokens_out", 0),
                "rate": message_data.get("rate", 0),

                # Timestamps
                "created_at":  AIServices._utc_iso(),
            }

            created = self.messages_container.create_item(doc_message)

            # Actualizar sesión (append message_id)
            session_id = message_data["session_id"]
            session = self.sessions_container.read_item(item=session_id, partition_key=session_id)
            session.setdefault("message", [])
            session["message"].append(message_data["message_id"])
            session["updated_at"] =  AIServices._utc_iso()

            self.sessions_container.replace_item(item=session_id, body=session)
            return created

        # =========================
        # QUERIES
        # =========================
        def get_user_sessions(self, user_id: str) -> List[Dict[str, Any]]:
            query = "SELECT * FROM c WHERE c.user_id = @user_id ORDER BY c.fecha_creacion DESC"
            params = [{"name": "@user_id", "value": user_id}]
            return list(self.sessions_container.query_items(query=query, parameters=params, enable_cross_partition_query=True))

        def get_session_messages(self, session_id: str) -> List[Dict[str, Any]]:
            query = "SELECT * FROM c WHERE c.id_session = @id_session ORDER BY c.created_at ASC"
            params = [{"name": "@id_session", "value": session_id}]
            return list(self.messages_container.query_items(query=query, parameters=params, enable_cross_partition_query=True))

        # =========================
        # ORQUESTACIÓN SIMPLE
        # =========================
        def save_answer_rag(
            self,
            session_id: str,
            user_id: str,
            user_question: str,
            ai_response,
            citations=None,
            file_path=None,
            tokens_in: int = 0,
            tokens_out: int = 0,
            extra: dict | None = None,
            channel: str = "web",
        ):
            if not self.session_exists(session_id):
                session_data = {
                    "session_id": session_id,
                    "user_id": user_id,
                    "session_name": generate_session_title(self.llm, user_question), 
                    "channel": channel
                }
                self.create_session(session_data)

            message_data = {
                "message_id": str(uuid.uuid4()),
                "session_id": session_id,
                "user_question": user_question,
                "ai_response": ai_response,
                "tokens_in": tokens_in,
                "tokens_out": tokens_out,
                "citations": citations or [],
                "file_path": file_path,
                "extra": extra or {}
            }
            self.save_message(message_data)
            self.touch_session(session_id)

        # =========================
        # DELETE
        # =========================
        def delete_session(self, session_id: str):
            """
            Elimina sesión y todos sus mensajes.
            messages container PK: /id_session
            sessions container PK: /id
            """
            try:
                # Mensajes de la sesión
                msg_query = "SELECT c.id, c.id_session FROM c WHERE c.id_session = @session_id"
                msg_params = [{"name": "@session_id", "value": session_id}]
                msg_items = list(self.messages_container.query_items(
                    query=msg_query,
                    parameters=msg_params,
                    enable_cross_partition_query=True
                ))

                deleted = 0
                for msg in msg_items:
                    try:
                        self.messages_container.delete_item(item=msg["id"], partition_key=msg["id_session"])
                        deleted += 1
                    except Exception as e:
                        logging.warning(f" Error eliminando mensaje {msg.get('id')}: {e}")

                logging.info(f"🧹 Se eliminaron {deleted} mensajes de la sesión {session_id}")

                # Borrar sesión
                try:
                    self.sessions_container.delete_item(item=session_id, partition_key=session_id)
                    logging.info(f"Sesión {session_id} eliminada.")
                except exceptions.CosmosResourceNotFoundError:
                    logging.info(f"ℹSesión {session_id} no encontrada (ya eliminada).")

            except Exception as e:
                logging.error(f"Error al eliminar sesión {session_id}: {e}")
                raise

        def count_uploaded_files(self, session_id: str) -> int:
            """
            Cuenta el total acumulado de archivos subidos en una sesión,
            sumando ARRAY_LENGTH(extra.uploaded_files) por cada mensaje.
            """
            query = """
            SELECT VALUE SUM(
                IIF(IS_DEFINED(c.extra.uploaded_files), ARRAY_LENGTH(c.extra.uploaded_files), 0)
            )
            FROM c
            WHERE c.id_session = @id_session
            """
            params = [{"name": "@id_session", "value": session_id}]
            items = list(self.messages_container.query_items(
                query=query,
                parameters=params,
                enable_cross_partition_query=True
            ))
            return int(items[0]) if items and items[0] is not None else 0
        
        def save_message_chat(
            self,
            session_id: str,
            user_id: str,
            user_question: str,
            ia_response: str,
            channel: str = "web",
            extra: dict | None = None,
        ):
            # Si no existe la sesión, créala (con título GPT)
            if not self.session_exists(session_id):
                session_data = {
                    "session_id": session_id,
                    "user_id": user_id,
                    "session_name": generate_session_title(self.llm, user_question),
                    "channel": channel
                }
                self.create_session(session_data)

            message_data = {
                "message_id": str(uuid.uuid4()),
                "session_id": session_id,
                "user_question": user_question,
                "ai_response": ia_response,
                "tokens_in": 0,
                "tokens_out": 0,
                "citations": [],
                "file_path": None,
                "extra": extra or {},
                "channel": channel,
            }

            self.save_message(message_data)
            self.touch_session(session_id)
