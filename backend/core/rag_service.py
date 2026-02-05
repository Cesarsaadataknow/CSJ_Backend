from openai import AzureOpenAI
from app.config import settings
from helpers.indexacion import EmbeddingService, AzureSearchIndexer

class RAGService:
    def __init__(self, embedder: EmbeddingService, indexer: AzureSearchIndexer) -> None:
        self.embedder = embedder
        self.indexer = indexer
        self.chat = AzureOpenAI(
            api_key=settings.AZURE_OPENAI_KEY,
            azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
            api_version=settings.AZURE_OPENAI_OPENAI_VERSION,
        )

    def answer(self, question: str, user_id: str, session_id: str, top_k: int = 6) -> dict:
        qvec = self.embedder.embed(question)
        hits = self.indexer.search_vectors(qvec, user_id=user_id, session_id=session_id, top_k=top_k)

        context = "\n\n".join(
            f"[{h.get('file_name')} | chunk {h.get('chunk_id')}] {h.get('content')}"
            for h in hits
        ).strip()

        system = (
            "Responde SOLO con base en el CONTEXTO. "
            "Si no está en el contexto, responde: 'No encuentro esa información en el documento subido'."
        )

        user = f"CONTEXTO:\n{context}\n\nPREGUNTA:\n{question}"

        resp = self.chat.chat.completions.create(
            model=settings.AZURE_OPENAI_CHAT_DEPLOYMENT,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.2,
        )

        return {
            "answer": resp.choices[0].message.content,
            "chunks_used": [
                {"file_name": h.get("file_name"), "chunk_id": h.get("chunk_id"), "file_id": h.get("file_id")}
                for h in hits
            ],
        }
