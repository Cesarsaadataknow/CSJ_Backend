from azure.search.documents import SearchClient
from azure.core.credentials import AzureKeyCredential
from app.config import settings

# Cliente global de Azure AI Search
search_client = SearchClient(
    endpoint=settings.AZURE_SEARCH_ENDPOINT,
    index_name=settings.AZURE_SEARCH_INDEX,
    credential=AzureKeyCredential(settings.AZURE_SEARCH_KEY)
)


def retrieve_from_index(query: str, top_k: int = 5):
    results = search_client.search(
        search_text=query,
        top=top_k
    )

    docs = []
    for r in results:
        docs.append({
            "id": r.get("id"),
            "texto": r.get("TEXTOPROVIDENCIA", "")
        })

    return docs


# from azure.search.documents import SearchClient
# from azure.core.credentials import AzureKeyCredential
# from app.config import settings

# search_client = SearchClient(
#     endpoint=settings.AZURE_SEARCH_ENDPOINT,
#     index_name=settings.AZURE_SEARCH_INDEX,
#     credential=AzureKeyCredential(settings.AZURE_SEARCH_KEY),
# )

# async def retrieve_from_index(query: str, top_k: int = 5):
#     results = search_client.search(
#         search_text=query,
#         top=top_k
#     )

#     documents = []
#     for r in results:
#         documents.append({
#             "id": r.get("id"),
#             "texto": r.get("content") or r.get("texto") or "",
#         })

#     return documents
