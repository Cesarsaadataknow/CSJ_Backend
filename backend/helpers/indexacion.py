import time
from typing import List, Dict
from azure.core.exceptions import ServiceRequestError, HttpResponseError
import tiktoken
from openai import AzureOpenAI
from azure.core.credentials import AzureKeyCredential
from azure.search.documents.models import VectorizedQuery
from azure.search.documents import SearchClient
from app.config import settings

from azure.search.documents.indexes.models import (
    SearchIndex, SearchField, SearchFieldDataType,
    VectorSearch, VectorSearchProfile, HnswAlgorithmConfiguration,
    SemanticConfiguration, SemanticPrioritizedFields, SemanticField,
    SimpleField
)


class AzureSearchIndexer:
    def __init__(self) -> None:
        self.client = SearchClient(
            endpoint=settings.AZURE_SEARCH_ENDPOINT,
            index_name=settings.AZURE_SEARCH_INDEX,
            credential=AzureKeyCredential(settings.AZURE_SEARCH_KEY),
        )

    def upload(self, docs: List[Dict], batch_size: int = 25, retries: int = 5) -> None:
        if not docs:
            return

        for i in range(0, len(docs), batch_size):
            batch = docs[i:i + batch_size]

            last_err = None
            for attempt in range(1, retries + 1):
                try:
                    res = self.client.upload_documents(documents=batch)
                    failed = [r for r in res if not r.succeeded]
                    if failed:
                        raise HttpResponseError(message=f"Fallaron docs: {failed[:3]} ...")
                    break  # OK
                except (ServiceRequestError, HttpResponseError) as e:
                    last_err = e
                    # backoff simple
                    time.sleep(min(2 ** attempt, 10))

            if last_err:
                raise last_err
            
    def list_session_files(self, user_id: str, session_id: str, top: int = 2000) -> list[dict]:
        """
        Devuelve lista única de archivos dentro de una sesión: [{file_id, file_name}, ...]
        """
        filter_expr = f"user_id eq '{user_id}' and session_id eq '{session_id}'"

        results = self.client.search(
            search_text="*",
            filter=filter_expr,
            top=top,
            select=["file_id", "file_name"]
        )

        seen = set()
        files = []
        for r in results:
            fid = r.get("file_id")
            fname = r.get("file_name")
            if not fid:
                continue
            key = (fid, fname)
            if key in seen:
                continue
            seen.add(key)
            files.append({"file_id": fid, "file_name": fname})

        return files
    
    def hybrid_search_by_file(
        self,
        question: str,
        query_vector: list[float],
        user_id: str,
        session_id: str,
        file_id: str,
        top_k: int = 4
    ) -> list[dict]:

        filter_expr = (
            f"user_id eq '{user_id}' and session_id eq '{session_id}' and file_id eq '{file_id}'"
        )

        vq = VectorizedQuery(
            vector=query_vector,
            k_nearest_neighbors=top_k,
            fields="content_vector",
        )

        results = self.client.search(
            search_text=question,
            search_mode="any",
            filter=filter_expr,
            top=top_k,
            vector_queries=[vq],
            select=["content", "file_name", "chunk_id", "file_id"]
        )

        return [r for r in results]

    def hybrid_search(self, question: str, query_vector: list[float], user_id: str, session_id: str, top_k: int = 6) -> list[dict]:
        filter_expr = f"user_id eq '{user_id}' and session_id eq '{session_id}'"

        vq = VectorizedQuery(
            vector=query_vector,
            k_nearest_neighbors=top_k,
            fields="content_vector",
        )

        results = self.client.search(
            search_text=question,     
            filter=filter_expr,
            top=top_k,
            vector_queries=[vq],     
            select=["content", "file_name", "chunk_id", "file_id"]
        )

        return [r for r in results]
    

class FabricSearchIndexer:
    def __init__(self) -> None:
        self.client = SearchClient(
            endpoint=settings.AZURE_SEARCH_ENDPOINT,
            index_name=settings.AZURE_SEARCH_INDEX_FABRIC,
            credential=AzureKeyCredential(settings.AZURE_SEARCH_KEY),
        )

    # def hybrid_search(self, pregunta_usuario):
    #     """
    #     Función que realiza una búsqueda híbrida (semántica + vectorial) en Azure Search
    #     y genera una respuesta amigable con GPT a partir de los resultados.
    #     """

    #     # Obtener configuración desde variables de entorno
    #     endpoint = os.getenv("AZURE_SEARCH_ENDPOINT")
    #     api_key = os.getenv("AZURE_SEARCH_API_KEY")
    #     index_name = os.getenv("AZURE_SEARCH_INDEX_NAME")
    #     semantic_config_name = "semantic-config"

    #     if not all([endpoint, api_key, index_name]):
    #         raise ValueError("Faltan variables de entorno para Azure Search")                                              

    #     # Embedding de la pregunta
    #     embedding_query = self.embedder.generar_embedding(pregunta_usuario)

    #     # Crear cliente de búsqueda
    #     client = SearchClient(
    #         endpoint=endpoint,
    #         index_name=index_name,
    #         credential=AzureKeyCredential(api_key)
    #     )

    #     # Preparar búsqueda híbrida usando VectorizedQuery
    #     vector_query = VectorizedQuery(
    #         vector=embedding_query,
    #         fields="embedding_resumen"
    #     )

    #     # Ejecutar búsqueda híbrida 
    #     resultados = list(client.search(
    #         search_text=pregunta_usuario,
    #         vector_queries=[vector_query],
    #         query_type="hibrid",
    #         semantic_configuration_name=semantic_config_name,
    #         top=3
    #     ))
    #     print(resultados)


    # def hybrid_search(self, question: str, query_vector: list[float], top_k: int = 10) -> list[dict]:
    #     vq = VectorizedQuery(
    #         vector=query_vector,
    #         k_nearest_neighbors=top_k,
    #         fields="texto_vector",
    #     )



    def hybrid_search(self, question: str, query_vector: list[float], top_k: int = 10) -> list[dict]:
            vq = VectorizedQuery(
                vector=query_vector,
                k_nearest_neighbors=top_k,
                fields="texto_vector",
            )


            results = self.client.search(
                search_text=question,
                search_mode="any",
                top=top_k,
                vector_queries=[vq],
                query_type="semantic",   # 👈 usar semantic
                semantic_configuration_name="semantic-config",  # 👈 nombre EXACTO
                select=[
                    "TEXTOPROVIDENCIA"
                ],
            )
            return [r for r in results]

        # results = self.client.search(
        #     search_text=question,
        #     vector_queries=[vq],
        #     query_type="simple",
        #     semantic_configuration_name="semantic_config",
        #     top=top_k,
        # )
        # return [r for r in results]


    # def hybrid_search(self, question: str, query_vector: list[float], top_k: int = 10) -> list[dict]:
    #     vq = VectorizedQuery(
    #         vector=query_vector,
    #         k_nearest_neighbors=top_k,
    #         fields="texto_vector",
    #     )


    #     results = self.client.search(
    #         search_text=question,
    #         search_mode="any",
    #         top=top_k,
    #         vector_queries=[vq],
    #         select=[
    #             "id", "texto", "chunk_order",
    #             "tipo_documento", "NaturalezaProceso", "claseProceso",
    #             "ACTOR", "DEMANDADO", "DECISION", "ProblemaJuridico"
    #         ],
    #     )
    #     return [r for r in results]




class EmbeddingService:
    def __init__(self) -> None:
        self.client = AzureOpenAI(
            api_key=settings.AZURE_OPENAI_KEY,
            azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
            api_version=settings.AZURE_OPENAI_OPENAI_VERSION,
        )
        self.deployment = settings.AZURE_OPENAI_EMBEDDING_DEPLOYMENT

    def embed(self, text: str) -> list[float]:
        text = (text or "").strip()
        if not text:
            return [0.0] * 3072
        resp = self.client.embeddings.create(model=self.deployment, input=text)
        return resp.data[0].embedding


class Chunker:
    def __init__(self, max_tokens: int = 900, overlap: int = 150) -> None:
        self.max_tokens = max_tokens
        self.overlap = overlap
        self.enc = tiktoken.get_encoding("cl100k_base")

    def split(self, text: str) -> list[str]:
        text = (text or "").strip()
        if not text:
            return []
        tokens = self.enc.encode(text)
        chunks: list[str] = []
        start = 0
        while start < len(tokens):
            end = min(start + self.max_tokens, len(tokens))
            chunk = self.enc.decode(tokens[start:end]).strip()
            if chunk:
                chunks.append(chunk)
            if end == len(tokens):
                break
            start = max(0, end - self.overlap)
        return chunks
