from openai import AzureOpenAI
from azure.ai.formrecognizer import DocumentAnalysisClient
from azure.core.credentials import AzureKeyCredential
from langchain_openai import AzureChatOpenAI, AzureOpenAIEmbeddings
from langchain.schema.messages import HumanMessage, SystemMessage
import asyncio
from langchain.text_splitter import RecursiveCharacterTextSplitter
import tiktoken
from typing import List, Tuple, Optional, Literal, Dict
from datetime import datetime, timedelta, timezone
from dateutil.parser import isoparse 
from azure.search.documents.indexes.aio import SearchIndexClient
from azure.search.documents.aio import SearchClient
from azure.search.documents.indexes.models import (
    SearchIndex,
    SimpleField,
    SearchField,
    SearchableField,
    SearchFieldDataType,
    VectorSearch,
    VectorSearchProfile,
    HnswAlgorithmConfiguration,
    SemanticConfiguration,
    SemanticPrioritizedFields,
    SemanticField,
    SemanticSearch
)
import hashlib
import base64
from datetime import datetime
from azure.core.exceptions import ResourceNotFoundError
from azure.cosmos.aio import CosmosClient
from azure.cosmos import exceptions
from azure.cosmos.exceptions import CosmosHttpResponseError, CosmosResourceNotFoundError
import time
import logging

from helpers.utils import format_conversation_data
from core.config import settings

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Ajusta el nivel de los loggers de terceros para que muestren solo WARNING o superior
logging.getLogger("azure").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("langchain-openai").setLevel(logging.WARNING)
logging.getLogger("openai").setLevel(logging.WARNING)

# Crear un logger propio para este módulo
logger = logging.getLogger("schema_services")
logger.setLevel(logging.INFO)

# Configurar un handler que imprima en la consola
handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

# Desactivar la propagación para que no se muestren logs de otros módulos
logger.propagate = False

class AIServices:
    class AzureOpenAI:
        def __init__(self, config:Optional[dict] = None):
            api_key: str = settings.ai_services.azure_openai_api_key
            api_version: str = settings.ai_services.openai_api_version
            azure_endpoint: str = settings.ai_services.azure_openai_endpoint
            azure_deployment = config.get("model_name") if config else settings.ai_services.model_gpt4o_name
            self._client_AzureOpenAI: AzureOpenAI = AzureOpenAI(
                api_key = api_key, 
                api_version = api_version,  
                azure_endpoint = azure_endpoint,
            )
            self.model_ai: AzureChatOpenAI = AzureChatOpenAI(
                api_key = api_key, 
                openai_api_version = api_version,
                azure_endpoint = azure_endpoint,
                azure_deployment = azure_deployment,
                reasoning_effort = config.get("reasoning_effort", None) if config else None,
                model_kwargs= {
                    "max_completion_tokens": config.get("max_completion_tokens", None) if config else None 
                }
            )
            self.model_embeddings: AzureOpenAIEmbeddings = AzureOpenAIEmbeddings(
                api_key = api_key, 
                openai_api_version = api_version,
                azure_endpoint = azure_endpoint,
                azure_deployment = settings.ai_services.model_embeddings_name
            )
            
        def analyze_image(self, image: bytes, msg: str = "Describe esta imagen:", mime_type: str = "image/jpeg") -> Dict:
            """
            Analiza una imagen utilizando el modelo de Azure OpenAI.
            
            :param image: Imagen en formato de bytes.
            :param msg: Mensaje adicional para el modelo.
            :param mime_type: Tipo MIME de la imagen (por defecto "image/jpeg").
            :return: Resultado del análisis de la imagen.
            """
            base64_image = base64.b64encode(image).decode("utf-8")
            image_url = f"data:{mime_type};base64,{base64_image}"
            messages = [
                SystemMessage(content="Eres un asistente experto en análisis de imágenes."),
                HumanMessage(content=[
                    {"type": "text", "text": msg},
                    {"type": "image_url", "image_url": {"url": image_url}}
                ])
            ]
            response = self.model_ai.invoke(messages)
            return {"response": response.content}

    class CosmosDBClient:
        def __init__(self):
            """
            Inicializa la conexión a Azure Cosmos DB.
            
            :param endpoint: URL del endpoint de Cosmos DB.
            :param key: Clave de autenticación para Cosmos DB.
            :param database_name: Nombre de la base de datos a utilizar.
            :param container_name: Nombre del contenedor a utilizar.
            """
            self.endpoint: str = settings.db_services.azure_cosmos_db_endpoint
            self.key: str = settings.db_services.azure_cosmos_db_api_key
            self.database_name: str = settings.db_services.azure_cosmos_db_name
            self.container_name: str = settings.db_services.azure_cosmos_db_container_name
            self.container_name_message_pairs: str = settings.db_services.azure_cosmos_db_container_name_message_pairs

            try:
                self.client = CosmosClient(self.endpoint, self.key)
                self.database = self.client.get_database_client(self.database_name)
                self.container = self.database.get_container_client(self.container_name)
                self.container_message_pairs=self.database.get_container_client(self.container_name_message_pairs)
                logging.info("Conexión a Cosmos DB establecida correctamente.")
            except CosmosHttpResponseError as e:
                logging.exception("Error al conectar con Cosmos DB: %s", str(e))
                raise

        async def query_documents(self, query: str) -> list[dict]:
            try:
                items = []
                async for item in self.container_message_pairs.query_items(
                    query=query  
                ):
                    items.append(item)
                return items
            except exceptions.CosmosHttpResponseError as e:
                logging.error(f"Error en query_documents: {str(e)}")
                return []

        async def create_document(self, document: dict) -> Optional[dict]:
            
            try:
                created_document = await self.container_message_pairs.create_item(body=document)
                logging.info(f"Documento creado con id: {created_document['id']}")
                return created_document
            except exceptions.CosmosHttpResponseError as e:
                logging.error(f"Error en create_document: {str(e)}")
                return None

        async def get_documents_by_thread_id(self, conversation_id: str) -> List[dict]:
            """
            Recupera todos los documentos que coinciden con el thread_id proporcionado.
            
            :param thread_id: El ID del thread para filtrar los documentos.
            :return: Lista de documentos que coinciden con el thread_id.
            """
            query = "SELECT * FROM c WHERE c.conversation_id = @conversation_id"
            parameters = [
                {"name": "@conversation_id", "value": conversation_id}
            ]

            try:
                items_iterator = self.container_message_pairs.query_items(
                    query=query,
                    parameters=parameters,
                )

                items = [item async for item in items_iterator]
                logging.info(f"Se recuperaron {len(items)} documentos para conversation_id: {conversation_id}")
                
                # 
                response = format_conversation_data(items)
                return response
            except CosmosHttpResponseError as e:
                logging.exception(f"Error al recuperar documentos para conversation_id {conversation_id}: {str(e)}")
                return []

        async def delete_documents_by_conversation_id(self, conversation_id: str) -> int:
            """
            Elimina todos los documentos que coinciden con el conversation_id proporcionado.

            :param conversation_id: El ID de la conversación.
            :return: Cantidad de documentos eliminados.
            """
            query = "SELECT c.id FROM c WHERE c.conversation_id = @conversation_id"
            parameters = [
                {"name": "@conversation_id", "value": conversation_id}
            ]

            try:
                # Buscar todos los documentos con ese conversation_id
                items_iterator = self.container_message_pairs.query_items(
                    query=query,
                    parameters=parameters,
                )

                deleted_count = 0

                async for item in items_iterator:
                    try:
                        await self.container_message_pairs.delete_item(
                            item=item["id"],
                            partition_key=conversation_id  # Asegúrate de usar el partition key correcto
                        )
                        deleted_count += 1
                    except CosmosHttpResponseError as e:
                        logging.warning(f"No se pudo eliminar el documento con id {item['id']}: {str(e)}")

                logging.info(f"Se eliminaron {deleted_count} documentos para conversation_id: {conversation_id}")
                return deleted_count

            except CosmosHttpResponseError as e:
                logging.exception(f"Error al eliminar documentos para conversation_id {conversation_id}: {str(e)}")
                return 0
            
        async def get_user_conversations(self, user_id: str) -> List[dict]:
            """
            Retorna una lista de conversaciones (conversation_id) para un user_id dado,
            junto con la fecha de creación (created_at) del primer mensaje registrado
            en cada conversación.
            """
            # Agregas `c.conversation_name` a la consulta si existe en tu documento
            query = """
                SELECT c.id, c.user_id, c.conversation_id, c.created_at, c.conversation_name
                FROM c
                WHERE c.user_id = @user_id
            """
            parameters = [
                {"name": "@user_id", "value": user_id}
            ]

            try:
                items_iterator = self.container_message_pairs.query_items(
                    query=query,
                    parameters=parameters
                )

                items = [item async for item in items_iterator]

                if len(items) == 0:
                    return None
                
                conversations_map = {}
                
                for doc in items:
                    conv_id = doc["conversation_id"]
                    # Usar get para evitar KeyError si no existe la clave
                    conversation_name = doc.get("conversation_name", "Conversación sin nombre definido")
                    doc_created_at = doc["created_at"]  

                    # Mantener el menor (más antiguo) created_at
                    if conv_id not in conversations_map:
                        conversations_map[conv_id] = {
                            "created_at": doc_created_at,
                            "conversation_name": conversation_name
                        }
                    else:
                        if doc_created_at < conversations_map[conv_id]["created_at"]:
                            conversations_map[conv_id]["created_at"] = doc_created_at

                # Convertir a lista
                result = []
                for conv_id, data in conversations_map.items():
                    result.append({
                        "conversation_id": conv_id,
                        "conversation_name": data["conversation_name"],
                        "created_at": data["created_at"]
                    })

                # Ordenar
                result.sort(key=lambda x: x["created_at"])

                return result

            except CosmosHttpResponseError as e:
                logging.exception(f"Error al obtener conversaciones para {user_id}: {str(e)}")
                return []
                
        # async def update_document_rate(
        #     self,
        #     document_id: str,
        #     rate: Literal[0, 1, 2],
        #     partition_key: Optional[str] = None
        #     ) -> Optional[int]:
        #     """
        #     Actualiza el valor del campo 'rate' de un documento específico con el valor proporcionado.
        #     - Si `rate == 2`, se eliminará el documento en lugar de actualizarlo.
        #     - Si el documento no existe, se harán reintentos con esperas crecientes (2s, 4s, 8s, 16s).
        #     Si después de 4 reintentos sigue sin existir, retorna None.

        #     :param document_id: El ID del documento a actualizar.
        #     :param rate: Valor que se asignará al campo 'rate' (1, 2 o 3).
        #     :param partition_key: La clave de partición del documento (si aplica).
        #     :return: El nuevo valor de 'rate' si la operación fue exitosa o None si no se encontró o hubo error.
        #     """

        #     # Tiempos de espera en segundos para cada uno de los reintentos
        #     retry_delays = [2, 4, 8, 16]

        #     for attempt, delay in enumerate(retry_delays, start=1):
        #         try:
        #             # Leer el documento utilizando la clave de partición apropiada.
        #             if partition_key:
        #                 document = await self.container_message_pairs.read_item(
        #                     item=document_id, 
        #                     partition_key=partition_key
        #                 )
        #             else:
        #                 # Asumiendo que 'id' es la clave de partición si no se proporciona otra
        #                 document = await self.container_message_pairs.read_item(
        #                     item=document_id, 
        #                     partition_key=document_id
        #                 )

        #             # Si el rate es 2, eliminamos el documento
        #             if rate == 2:
        #                 await self.container_message_pairs.delete_item(
        #                     item=document_id,
        #                     partition_key=partition_key if partition_key else document_id
        #                 )
        #                 logging.info(f"Documento {document_id} eliminado exitosamente porque rate==2.")
        #                 return 2  # Retornamos 2 para indicar que se cumplió la operación de borrado

        #             # Caso contrario, actualizamos el rate y la fecha
        #             document['rate'] = rate
        #             document['updated_at'] = datetime.now().isoformat()

        #             # Reemplazar el documento en Cosmos DB con los cambios
        #             await self.container_message_pairs.replace_item(
        #                 item=document_id,
        #                 body=document
        #             )

        #             logging.info(f"Documento {document_id} actualizado exitosamente con rate={rate}.")
        #             return rate

        #         except CosmosResourceNotFoundError:
        #             logging.warning(
        #                 f"({attempt}° intento) Documento con id {document_id} no encontrado. "
        #                 f"Reintentando en {delay} segundos..."
        #             )
        #             # Esperamos antes de reintentar
        #             await asyncio.sleep(delay)

        #         except CosmosHttpResponseError as e:
        #             logging.exception(f"Error al actualizar/eliminar el documento {document_id}: {str(e)}")
        #             return None

        #     # Si llegamos aquí, es porque agotamos los reintentos y no se encontró el documento
        #     logging.error(f"No se pudo encontrar el documento {document_id} después de varios intentos.")
        #     return None
        
        async def update_document_rate(
            self,
            document_id: str,
            rate: Literal[0, 1, 2],
            partition_key: Optional[str] = None
        ) -> Optional[int]:
            """
            Actualiza el valor del campo 'rate' de un documento específico.
            Si el documento existe, se actualiza su valor y se modifica el campo 'updated_at'.
            Si el documento no existe, se crea inmediatamente con los campos 'rate', 'created_at' y 'updated_at'.

            :param document_id: ID del documento.
            :param rate: Valor que se asignará al campo 'rate' (0, 1 o 2).
            :param partition_key: Clave de partición del documento (si aplica).
            :return: El valor de 'rate' si la operación fue exitosa, o None en caso de error.
            """
            try:
                # Intentamos leer el documento existente
                if partition_key:
                    document = await self.container_message_pairs.read_item(
                        item=document_id, 
                        partition_key=partition_key
                    )
                else:
                    # Asumimos que 'id' es la clave de partición si no se proporciona otra
                    document = await self.container_message_pairs.read_item(
                        item=document_id, 
                        partition_key=document_id
                    )

                # Actualizamos el campo 'rate' y la fecha de actualización
                document['rate'] = rate
                document['updated_at'] = datetime.now().isoformat()

                # Reemplazamos el documento en Cosmos DB con los cambios realizados
                await self.container_message_pairs.replace_item(
                    item=document_id,
                    body=document
                )

                logging.info(f"Documento {document_id} actualizado exitosamente con rate={rate}.")
                return rate

            except CosmosResourceNotFoundError:
                # Si el documento no existe, lo creamos inmediatamente
                now = datetime.now().isoformat()
                new_document = {
                    "id": document_id,
                    "rate": rate,
                    "created_at": now,
                    "updated_at": now
                }

                # Si se proporciona partition_key, se puede incluir en el documento según la configuración de tu contenedor
                if partition_key:
                    new_document["conversation_id"] = partition_key

                try:
                    await self.container_message_pairs.create_item(new_document)
                    logging.info(f"Documento {document_id} creado exitosamente con rate={rate}.")
                    return rate
                except CosmosHttpResponseError as e:
                    logging.exception(f"Error al crear el documento {document_id}: {str(e)}")
                    return None

            except CosmosHttpResponseError as e:
                logging.exception(f"Error al actualizar el documento {document_id}: {str(e)}")
                return None

        def delete_document(self, document_id: str, partition_key: Optional[str] = None) -> bool:
            """
            Elimina un documento específico de Cosmos DB.
            
            :param document_id: El ID del documento a eliminar.
            :param partition_key: La clave de partición del documento (si aplica).
            :return: True si la eliminación fue exitosa, False en caso contrario.
            """
            try:
                if partition_key:
                    self.container.delete_item(item=document_id, partition_key=partition_key)
                else:
                    self.container.delete_item(item=document_id, partition_key=document_id)
                logging.info(f"Documento {document_id} eliminado exitosamente.")
                return True
            except exceptions.CosmosResourceNotFoundError:
                logging.warning(f"Documento con id {document_id} no encontrado para eliminar.")
                return False
            except CosmosHttpResponseError as e:
                logging.exception(f"Error al eliminar el documento {document_id}: {str(e)}")
                return False

    class AzureDocumentIntelligence:
        def __init__(self):
            
            api_key: str = settings.ai_services.document_intelligence_key
            api_version: str = settings.ai_services.document_intelligence_api_version
            document_intelligence_endpoint: str = settings.ai_services.document_intelligence_endpoint
            
            self.document_analysis_client = DocumentAnalysisClient(
                                                                    endpoint=document_intelligence_endpoint, 
                                                                    credential=AzureKeyCredential(key=api_key), 
                                                                    apiversion=api_version
            )
            
        def analyze_read(self, file_obj=None):
            """
            Analiza el contenido de un documento PDF proporcionado como un objeto de archivo en memoria.

            param file_obj: Objeto de archivo en memoria para analizar (BytesIO, por ejemplo).
            return: Lista con el texto extraído de cada página.
            """
            if file_obj is None:
                raise ValueError("Debe proporcionarse 'file_obj'.")

            try:
                # Llama al modelo "prebuilt-read" para extraer contenido del archivo PDF
                poller = self.document_analysis_client.begin_analyze_document(
                    "prebuilt-read", document=file_obj
                )
                result = poller.result()
                
                full_content_list = []
                for page in result.pages:
                    # Extrae líneas de texto por página
                    page_text_lines = [line.content for line in page.lines]
                    page_text = ' '.join(page_text_lines)
                    full_content_list.append(page_text)

                return full_content_list

            except Exception as e:
                raise RuntimeError(f"Error al analizar el PDF: {e}")  

    class AzureAiSearch:
        def __init__(self):
            self.search_endpoint: str = settings.ai_services.azure_search_endpoint
            self.search_key: str = settings.ai_services.azure_search_key
            self.search_credential = AzureKeyCredential(self.search_key)

        async def create_upload_index(self, docs: List[dict] = None, fields: List[SearchField] = None, vector_search: VectorSearch = None, semantic_config: SemanticConfiguration = None, index_name: str = "index_name"):
            async with SearchIndexClient(
                endpoint=self.search_endpoint,
                credential=self.search_credential
            ) as index_client:

                if not fields:
                    fields = [
                        SimpleField(name="id", type=SearchFieldDataType.String, key=True),
                        SearchableField(name="file_name", type=SearchFieldDataType.String, filterable=True),
                        SearchableField(name="page_content", type=SearchFieldDataType.String, filterable=True),
                        SimpleField(name="last_update", type=SearchFieldDataType.DateTimeOffset, filterable=True),
                        SimpleField(name="count_tokens", type=SearchFieldDataType.Int64, filterable=True),
                        SearchField(
                            name="content_vector",
                            type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
                            searchable=True,
                            vector_search_dimensions=1536,
                            vector_search_profile_name="myHnswProfile",
                        ),
                        SearchField(
                            name="user_id",
                            type=SearchFieldDataType.String,
                            filterable=True
                        ),
                        SearchField(
                            name="conversation_id",
                            type=SearchFieldDataType.String,
                            filterable=True
                        )
                    ]

                if not vector_search:
                    vector_search = VectorSearch(
                        algorithms=[HnswAlgorithmConfiguration(name="myHnsw")],
                        profiles=[
                            VectorSearchProfile(
                                name="myHnswProfile",
                                algorithm_configuration_name="myHnsw"
                            )
                        ],
                    )

                if not semantic_config:
                    semantic_config = SemanticConfiguration(
                        name="my-semantic-config",
                        prioritized_fields=SemanticPrioritizedFields(
                            title_field=SemanticField(field_name="file_name"),
                        ),
                    )

                semantic_search = SemanticSearch(configurations=[semantic_config])

                try:
                    index = SearchIndex(
                        name=index_name,
                        fields=fields,
                        vector_search=vector_search,
                        semantic_search=semantic_search,
                    )

                    result = await index_client.create_or_update_index(index)
                    print(f"Index {result.name} created/updated")
                    logging.info(f"Index {result.name} created/updated")

                    if docs:
                        async with SearchClient(
                            endpoint=self.search_endpoint,
                            index_name=index_name,
                            credential=self.search_credential
                        ) as search_client:
                            _ = await search_client.upload_documents(docs)
                            print(f"Uploaded {len(docs)} documents")
                            logging.info(f"Uploaded {len(docs)} documents")

                except Exception as e:
                    logging.exception("Error al crear o actualizar el índice: %s", str(e))

        async def get_all_document_ids(self, index_name: str, conversation_id: str) -> List[str]:
            try:
                async with SearchClient(
                    endpoint=self.search_endpoint,
                    index_name=index_name,
                    credential=self.search_credential
                ) as search_client:
                    document_ids = []

                    results = await search_client.search(
                        search_text="*",
                        filter=f"conversation_id eq '{conversation_id}'",
                        select=["id","last_update"],
                        top=100000
                    )
                    async for result in results:
                        document_ids.append({"id": result["id"],
                                            "last_update": result["last_update"]})

                    return document_ids

            except Exception as e:
                logging.warning(f"Error retrieving document IDs from index '{index_name}': {str(e)}")
                return []

        async def process_hash_ids(self, conversation_id, index_name: str, hash_ids_list: List[str]) -> Tuple[List[str], List[str], List[str]]:
            logging.info("Proceso de Indexación Automática Iniciado")

            input_hash_ids = set(hash_ids_list)

            index_created = await self.index_exists(index_name)
            if not index_created:
                logging.warning(f"El índice '{index_name}' no existe en Azure Search.")
                return hash_ids_list, [], []
            
            all_documents_ids = await self.get_all_document_ids(index_name, conversation_id)
            only_ids = [item['id'] for item in all_documents_ids]
            existing_hash_ids = set(only_ids)

            new_hash_ids = input_hash_ids - existing_hash_ids
            already_existing_hash_ids = list(input_hash_ids & existing_hash_ids)
            # Obtener la fecha y hora actual en UTC
            now_time = datetime.now(timezone.utc)

            # Filtrar los documentos cuya diferencia sea mayor a 24 horas
            to_delete_hashes_ids = [
                item['id']
                for item in all_documents_ids
                if now_time - isoparse(item['last_update']) > timedelta(hours=24)
            ]

            return list(new_hash_ids), already_existing_hash_ids, to_delete_hashes_ids

        async def index_exists(self, index_name: str) -> bool:
            async with SearchIndexClient(
                endpoint=self.search_endpoint,
                credential=self.search_credential
            ) as index_client:
                try:
                    await index_client.get_index(index_name)
                    return True
                except ResourceNotFoundError:
                    return False
                except Exception as e:
                    logging.exception(f"Error consultando existencia del índice '{index_name}': {str(e)}")
                    raise
    
        async def delete_documents_by_ids(self, index_name: str, document_ids: List[str]) -> bool:
            async with SearchClient(
                endpoint=self.search_endpoint,
                index_name=index_name,
                credential=self.search_credential
            ) as search_client:

                documents_to_delete = [{"id": doc_id} for doc_id in document_ids]

                try:
                    result = await search_client.delete_documents(documents=documents_to_delete)
                    return True if result else False
                except Exception as e:
                    logging.exception(f"Error al eliminar documentos: {str(e)}")
                    return False
                
        async def search_documents_in_index(self, index_name: str, search_text: str, conversation_id: str) -> List[dict]:
            """
            Realiza una búsqueda en un índice de Azure Cognitive Search y devuelve los documentos encontrados.

            :param index_name: Nombre del índice a consultar.
            :param search_text: Texto de búsqueda.
            :param conversation_id: ID de la conversación.
            :return: Lista de diccionarios con los resultados de la búsqueda.
            """

            documents = []
            async with SearchClient(
                endpoint=self.search_endpoint,
                index_name=index_name,
                credential=self.search_credential
            ) as search_client:

                results = await search_client.search(search_text=search_text, filter=f"conversation_id eq '{conversation_id}'", top=10, select=['file_name', 'page_content'])
                async for result in results:
                    documents.append(result)
            

            logging.info(f"Se encontraron {len(documents)} documentos en la búsqueda.")
            return documents
    
        async def delete_old_documents(self, index_name: str = "chat-index", days: int = 15) -> bool:
            """
            Elimina documentos del índice cuyo campo 'last_update' sea anterior a la fecha límite definida en 'days'.
            
            :param index_name: Nombre del índice de Azure AI Search.
            :param days: Número de días para considerar un documento como obsoleto (por defecto 30 días).
            :return: True si la eliminación se realizó correctamente o no se encontró documentos obsoletos, False en caso contrario.
            """
            # Calcular la fecha límite (30 días atrás) y formatearla sin microsegundos
            threshold_date = datetime.now(timezone.utc) - timedelta(days=days)
            threshold_str = threshold_date.strftime("%Y-%m-%dT%H:%M:%SZ")
            
            logging.info("Iniciando eliminación de documentos anteriores a %s", threshold_str)
            document_ids = []
            try:
                async with SearchClient(
                    endpoint=self.search_endpoint,
                    index_name=index_name,
                    credential=self.search_credential
                ) as search_client:
                    # Usar la fecha literal sin comillas ni prefijo
                    results = await search_client.search(
                        search_text="*",
                        filter=f"last_update lt {threshold_str}",
                        select=["id", "last_update"],
                        top=100000
                    )
                    async for result in results:
                        document_ids.append(result["id"])
            except Exception as e:
                logging.exception("Error al consultar documentos para eliminación: %s", str(e))
                return False

            if document_ids:
                logging.info("Se encontraron %d documentos para eliminar.", len(document_ids))
                success = await self.delete_documents_by_ids(index_name, document_ids)
                if success:
                    logging.info("Eliminación de %d documentos antiguos completada exitosamente.", len(document_ids))
                else:
                    logging.warning("Ocurrió un error durante la eliminación de documentos antiguos.")
                return success
            else:
                logging.info("No se encontraron documentos obsoletos para eliminar en el índice %s.", index_name)
                return True

    class PdfProcessor:
        def __init__(self):
            self.document_intelligence_service = AIServices.AzureDocumentIntelligence()
            self.azure_ai_search_service = AIServices.AzureAiSearch()
            self.azure_openai_service = AIServices.AzureOpenAI()

        async def main(self, user_id, conversation_id, files_obj: list = None):
            """
            Analiza el contenido de un documento PDF proporcionado como un objeto de archivo en memoria.
            """
            logger.info("Inicio del método main de PdfProcessor.")
            inicio_main = time.perf_counter()

            if files_obj is None:
                raise ValueError("Debe proporcionarse 'file_obj'.")

            # Procesar archivos en paralelo
            logger.info("Iniciando procesamiento paralelo de archivos...")
            tasks = [self._process_file(file) for file in files_obj]
            processed_files = await asyncio.gather(*tasks)
            logger.info("Procesamiento individual de archivos completado.")

            read_files = []
            unread_files = []
            for file_name, extracted_content, message in processed_files:
                if extracted_content:
                    read_files.append({
                        "file_name": file_name,
                        "message": message,
                        "content": extracted_content
                    })
                else:
                    unread_files.append({
                        "file_name": file_name,
                        "message": message
                    })

            text_content = [res.get("content") for res in read_files]

            # Contar tokens del texto
            logger.info("Iniciando conteo de tokens de los textos extraídos.")
            encoder = tiktoken.get_encoding("cl100k_base")
            count_tokens = len(encoder.encode(str(text_content)))
            max_tokens_input_model = 0  # Define un valor apropiado

            if count_tokens > max_tokens_input_model:
                # Chunkear textos extraídos
                logger.info("Inicio de chunking de textos extraídos.")
                inicio_chunk = time.perf_counter()
                chunks = self.chunk_extracted_texts(user_id=user_id, extracted_files=read_files)
                fin_chunk = time.perf_counter()
                logger.info("Fin de chunking de textos. Tiempo: %.4f segundos", fin_chunk - inicio_chunk)

                hash_ids_list = [doc.metadata.get("id") for doc in chunks]
                logger.info("Inicio de process_hash_ids en AzureAiSearch.")
                inicio_hash = time.perf_counter()
                new_hash_ids, already_existing_hash_ids, to_delete_hashes_ids = await self.azure_ai_search_service.process_hash_ids(
                    conversation_id=conversation_id,
                    index_name="chat-index",
                    hash_ids_list=hash_ids_list
                )
                index_info = {
                    "num_added": len(new_hash_ids),
                    "num_skipped": len(already_existing_hash_ids),
                    "num_deleted": len(to_delete_hashes_ids)
                }
                print(f"\033[32mResultado esperado del proceso de verificación de hashes:\n{index_info}\033[0m")
                fin_hash = time.perf_counter()
                logger.info("Fin de process_hash_ids. Índice info: %s. Tiempo: %.4f segundos", index_info, fin_hash - inicio_hash)

                # Filtrar solo los documentos nuevos
                docs = [doc for doc in chunks if doc.metadata.get("id") in new_hash_ids]

                if to_delete_hashes_ids:
                    asyncio.create_task(
                        self.azure_ai_search_service.delete_documents_by_ids(
                            index_name="chat-index", document_ids=to_delete_hashes_ids
                        )
                    )

                # Procesar embeddings en paralelo (si embed_query es síncrono, lo ejecutamos en un thread)
                logger.info("Inicio de procesamiento paralelo de embeddings.")
                inicio_embed = time.perf_counter()

                embed_tasks = [
                    asyncio.to_thread(self.azure_openai_service.model_embeddings.embed_query, doc.page_content)
                    for doc in docs
                ]
                embeddings = await asyncio.gather(*embed_tasks)
                fin_embed = time.perf_counter()
                logger.info("Fin de procesamiento de embeddings. Tiempo: %.4f segundos", fin_embed - inicio_embed)

                ldocs = []
                for doc, embedding in zip(docs, embeddings):
                    ldocs.append({
                        "id": doc.metadata.get("id"),
                        "user_id": user_id,
                        "conversation_id": conversation_id,
                        "file_name": doc.metadata.get("file_name"),
                        "page_content": doc.page_content,
                        "content_vector": embedding,
                        "last_update": datetime.now(),
                        "count_tokens": len(encoder.encode(doc.page_content))
                    })
                logger.info("Iniciando la creación/actualización del índice en Azure AI Search.")
                inicio_index = time.perf_counter()

                await self.azure_ai_search_service.create_upload_index(docs=ldocs, index_name="chat-index")
                fin_index = time.perf_counter()
                logger.info("Fin de creación/actualización del índice. Tiempo: %.4f segundos", fin_index - inicio_index)

                fin_main = time.perf_counter()
                logger.info("Fin del método main de PdfProcessor. Tiempo total: %.4f segundos", fin_main - inicio_main)

            else:
                # Si es lo suficientemente "pequeña" para el LLM, se puede procesar de otra forma
                pass

            response = {
                "user_id": user_id,
                "read_files": [
                    {"file_name": res.get("file_name"), "message": res.get("message")}
                    for res in read_files
                ],
                "unread_files": [res.get("file_name") for res in unread_files]
            }
            return text_content, response

        async def _process_file(self, file):
            """
            Procesa individualmente un archivo. Si es PDF se utiliza analyze_read, de lo contrario
            se devuelve el contenido directamente.
            """
            
            file_name = file.get("file_name")
            logger.info("Inicio de _process_file para el archivo: %s", file_name)
            inicio_proc = time.perf_counter()

            doc_type = file.get("doc_type")
            content = file.get("content")
            
            # Usar Azure Form Recognizer (analyze_read) para PDF, imágenes y PPTX
            if doc_type in ["pdf"]:
                extracted_content = await asyncio.to_thread(
                    self.document_intelligence_service.analyze_read,
                    content
                )
            else:
                # Texto, Word, Excel, etc. (ya procesado en el endpoint)
                extracted_content = content

            message = (
                f"Archivo {file_name} procesado correctamente"
                if extracted_content
                else f"No se pudo extraer el contenido del archivo {file_name}"
            )
            fin_proc = time.perf_counter()
            logger.info("Fin de _process_file para el archivo: %s. Tiempo: %.4f segundos", file_name, fin_proc - inicio_proc)

            return file_name, extracted_content, message

        def chunk_extracted_texts(
            self,
            user_id: str,
            extracted_files: list,
            chunk_size: int = 5000,
            chunk_overlap: int = 200
        ) -> list:
            """
            Combina y divide el texto de cada archivo en chunks.
            """
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap
            )
            splitted_docs = []
            for file_info in extracted_files:
                file_name = file_info.get("file_name")
                # Combinar todas las páginas en un solo string
                combined_text = (
                    "\n".join(file_info.get("content", []))
                    if isinstance(file_info.get("content"), list)
                    else str(file_info.get("content"))
                )
                # Crear los documentos troceados
                docs = text_splitter.create_documents(
                    texts=[combined_text],
                    metadatas=[{"file_name": file_name}]
                )
                for doc in docs:
                    string_to_hash = f"{user_id}-{doc.page_content}"
                    doc.metadata["id"] = hashlib.sha256(string_to_hash.encode()).hexdigest()
                splitted_docs.extend(docs)
            return splitted_docs
    
    # class DatalakeStorage:
    #     """
    #     Clase para conectarse a Azure Data Lake Storage y descargar contenido (por ejemplo, prompts).
    #     """

    #     def __init__(self):
    #         """
    #         Inicializa la conexión al Data Lake de Azure, tomando las claves del archivo de configuración.
    #         """
    #         settings = Settings()
    #         connection_string: str = settings.AIServices().azure_datalake_connection_string
    #         filesystem_name: str = settings.AIServices().azure_datalake_filesystem_name

    #         self._service_client: DataLakeServiceClient = DataLakeServiceClient.from_connection_string(
    #             connection_string
    #         )
    #         self._file_system_client = self._service_client.get_file_system_client(
    #             file_system=filesystem_name
    #         )

    #     def download_file_content(self, file_path: str) -> str:
    #         """
    #         Descarga y retorna el contenido de un archivo de texto almacenado en el Data Lake.
    #         """
    #         print("Downloading file content...")
    #         file_client = self._file_system_client.get_file_client(file_path)
    #         download = file_client.download_file()
    #         content = download.readall()
    #         return content.decode('utf-8')

    #     def list_files_in_directory(self, directory_path: str) -> list:
    #         """
    #         Lista todos los archivos dentro de un directorio específico en el Data Lake.
    #         """
    #         print("Listing files in directory...")
    #         paths = self._file_system_client.get_paths(path=directory_path)
    #         files = []
    #         for path in paths:
    #             # Verificamos que no sea un directorio
    #             if not path.is_directory:
    #                 files.append(path.name)
    #         return files

    #     def download_prompts_from_directory(self, directory_path: str) -> dict:
    #         """
    #         Descarga el contenido de todos los archivos (por ejemplo, prompts) dentro de un directorio,
    #         retornando un diccionario donde la clave es el nombre del archivo y el valor es su contenido.
    #         """
    #         print("Downloading all prompts from directory...")
    #         files = self.list_files_in_directory(directory_path)
    #         prompts = {}
    #         for file in files:
    #             content = self.download_file_content(file)
    #             file_name = file.split('/')[-1]  # Extraemos solo el nombre del archivo
    #             prompts[file_name] = content
    #         return prompts
    def __init__(self):
        self.service_azure_open_ai = AIServices.AzureOpenAI()
