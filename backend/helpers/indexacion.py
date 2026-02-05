import time
from typing import List, Dict
from azure.core.exceptions import ServiceRequestError, HttpResponseError
import tiktoken
from openai import AzureOpenAI
from azure.core.credentials import AzureKeyCredential
from azure.search.documents.models import VectorizedQuery
from azure.search.documents import SearchClient
from app.config import settings


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


    def search_vectors(self, query_vector: list[float], user_id: str, session_id: str, top_k: int = 6) -> list[dict]:
        filter_expr = f"user_id eq '{user_id}' and session_id eq '{session_id}'"

        vector_query = VectorizedQuery(
            vector=query_vector,
            k_nearest_neighbors=top_k,
            fields="content_vector"
        )

        results = self.client.search(
            search_text=None,  
            filter=filter_expr,
            top=top_k,
            vector_queries=[vector_query],
            select=["content", "file_name", "chunk_id", "file_id"]
        )

        return [r for r in results]


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
