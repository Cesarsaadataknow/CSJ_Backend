from azure.search.documents import SearchClient
from azure.core.credentials import AzureKeyCredential
from app.config import settings


search_client_docs = SearchClient(
    endpoint=settings.AZURE_SEARCH_ENDPOINT,
    index_name=settings.AZURE_SEARCH_DOCS_INDEX,
    credential=AzureKeyCredential(settings.AZURE_SEARCH_KEY),
)


def retrieve_docs(query: str, top_k: int = 5):
    results = search_client_docs.search(
        search_text=query,
        top=top_k
    )

    docs = []

    for r in results:
        content = r.get("content", "")

        if not content:
            continue

        docs.append({
            "id": r.get("id"),
            "texto": content,
            "score": r.get("@search.score"),
            "filename": r.get("filename", "")
        })

    return docs
