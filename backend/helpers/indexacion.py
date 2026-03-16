import re
import time
from typing import List, Dict

import tiktoken
from openai import AzureOpenAI
from azure.core.credentials import AzureKeyCredential
from azure.core.exceptions import ServiceRequestError, HttpResponseError
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
                    last_err = None
                    break
                except (ServiceRequestError, HttpResponseError) as e:
                    last_err = e
                    time.sleep(min(2 ** attempt, 10))

            if last_err:
                raise last_err

    def list_session_files(self, user_id: str, session_id: str, top: int = 2000) -> list[dict]:
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
            query_type="semantic",
            semantic_configuration_name="semantic-config-docs",
            select=[
                "content",
                "file_name",
                "chunk_id",
                "file_id",
                "page_number",
                "needs_ai",
                "ai_reason",
                "has_figures",
                "figures_count",
                "tables_count",
                "has_complex_table",
                "tables_marked_for_ai",
            ],
        )
        return [dict(r) for r in results]

    def hybrid_search(
        self,
        question: str,
        query_vector: list[float],
        user_id: str,
        session_id: str,
        top_k: int = 6
    ) -> list[dict]:
        filter_expr = f"user_id eq '{user_id}' and session_id eq '{session_id}'"

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
            query_type="semantic",
            semantic_configuration_name="semantic-config-docs",
            select=[
                "content",
                "file_name",
                "chunk_id",
                "file_id",
                "page_number",
                "needs_ai",
                "ai_reason",
                "has_figures",
                "figures_count",
                "tables_count",
                "has_complex_table",
                "tables_marked_for_ai",
            ],
        )

        return [dict(r) for r in results]


class FabricSearchIndexer:
    def __init__(self) -> None:
        self.credential = AzureKeyCredential(settings.AZURE_SEARCH_KEY)

        self.client_fabric = SearchClient(
            endpoint=settings.AZURE_SEARCH_ENDPOINT,
            index_name=settings.AZURE_SEARCH_INDEX_FABRIC,
            credential=self.credential,
        )

        self.client_xls = SearchClient(
            endpoint=settings.AZURE_SEARCH_ENDPOINT,
            index_name=settings.AZURE_SEARCH_INDEX_XLS,
            credential=self.credential,
        )

    def _search_one(
        self,
        client: SearchClient,
        question: str,
        query_vector: list[float],
        top_k: int,
        select_fields: list[str],
        source_tag: str,
    ) -> list[dict]:
        vq = VectorizedQuery(
            vector=query_vector,
            k_nearest_neighbors=top_k,
            fields="texto_vector",
        )

        results = client.search(
            search_text=question,
            search_mode="any",
            top=top_k,
            vector_queries=[vq],
            query_type="semantic",
            semantic_configuration_name="semantic-config",
            select=select_fields,
        )

        out = []
        for r in results:
            d = dict(r)
            d["_source_index"] = source_tag
            out.append(d)
        return out

    def hybrid_search(self, question: str, query_vector: list[float], top_k: int = 10) -> list[dict]:
        hits_fabric = self._search_one(
            client=self.client_fabric,
            question=question,
            query_vector=query_vector,
            top_k=top_k,
            select_fields=["TEXTOPROVIDENCIA"],
            source_tag="fabric",
        )

        hits_xls = self._search_one(
            client=self.client_xls,
            question=question,
            query_vector=query_vector,
            top_k=top_k,
            select_fields=["contenido"],
            source_tag="xls",
        )

        merged = hits_fabric + hits_xls
        seen = set()
        final_hits = []
        for h in merged:
            key = (h.get("id"), h.get("_source_index"))
            if key in seen:
                continue
            seen.add(key)
            final_hits.append(h)

        return final_hits


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
    """
    Chunker estructurado:
    - Respeta bloques especiales como [TABLA], [FIGURA], [DESCRIPCIÓN_VISUAL], [PÁGINA]
    - Intenta no cortar tablas complejas
    - Si un bloque es demasiado grande, hace split por tokens
    """

    BLOCK_HEADER_RE = re.compile(
        r"(?=^\[(?:PÁGINA|TEXTO|TABLA.*?|FIGURA.*?|DESCRIPCIÓN_VISUAL|HEADER_ROW_\d+|ROW_\d+|DIMENSIONES)\])",
        re.MULTILINE,
    )

    def __init__(self, max_tokens: int = 900, overlap: int = 150) -> None:
        self.max_tokens = max_tokens
        self.overlap = overlap
        self.enc = tiktoken.get_encoding("cl100k_base")

    def split(self, text: str) -> list[str]:
        text = (text or "").strip()
        if not text:
            return []

        blocks = self._split_into_blocks(text)
        if not blocks:
            return self._split_by_tokens(text)

        chunks: list[str] = []
        current_parts: list[str] = []

        for block in blocks:
            candidate = self._join_parts(current_parts + [block])

            if not current_parts:
                if self._count_tokens(block) <= self.max_tokens:
                    current_parts.append(block)
                else:
                    chunks.extend(self._split_large_block(block))
                continue

            if self._count_tokens(candidate) <= self.max_tokens:
                current_parts.append(block)
            else:
                current_chunk = self._join_parts(current_parts)
                if current_chunk:
                    chunks.append(current_chunk)

                if self._count_tokens(block) <= self.max_tokens:
                    current_parts = [block]
                else:
                    chunks.extend(self._split_large_block(block))
                    current_parts = []

        if current_parts:
            final_chunk = self._join_parts(current_parts)
            if final_chunk:
                chunks.append(final_chunk)

        return [c.strip() for c in chunks if c.strip()]

    def _split_into_blocks(self, text: str) -> list[str]:
        """
        Separa por bloques etiquetados.
        """
        parts = self.BLOCK_HEADER_RE.split(text)
        blocks = [p.strip() for p in parts if p and p.strip()]
        return blocks

    def _split_large_block(self, block: str) -> list[str]:
        """
        Si un bloque es muy grande:
        - primero intenta partir por líneas
        - si no alcanza, parte por tokens
        """
        lines = [ln.strip() for ln in block.splitlines() if ln.strip()]
        if not lines:
            return self._split_by_tokens(block)

        chunks: list[str] = []
        current_lines: list[str] = []

        for line in lines:
            candidate = "\n".join(current_lines + [line]).strip()
            if not current_lines:
                if self._count_tokens(line) <= self.max_tokens:
                    current_lines.append(line)
                else:
                    chunks.extend(self._split_by_tokens(line))
                continue

            if self._count_tokens(candidate) <= self.max_tokens:
                current_lines.append(line)
            else:
                chunk = "\n".join(current_lines).strip()
                if chunk:
                    chunks.append(chunk)

                if self._count_tokens(line) <= self.max_tokens:
                    current_lines = [line]
                else:
                    chunks.extend(self._split_by_tokens(line))
                    current_lines = []

        if current_lines:
            chunk = "\n".join(current_lines).strip()
            if chunk:
                chunks.append(chunk)

        return chunks

    def _split_by_tokens(self, text: str) -> list[str]:
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

    def _count_tokens(self, text: str) -> int:
        return len(self.enc.encode(text or ""))

    def _join_parts(self, parts: list[str]) -> str:
        return "\n\n".join(p.strip() for p in parts if p and p.strip()).strip()