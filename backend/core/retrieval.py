from azure.search.documents import SearchClient
from azure.core.credentials import AzureKeyCredential
from app.config import settings


search_client_docs = SearchClient(
    endpoint=settings.AZURE_SEARCH_ENDPOINT,
    index_name=settings.AZURE_SEARCH_DOCS_INDEX,
    credential=AzureKeyCredential(settings.AZURE_SEARCH_KEY)
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



# from azure.search.documents import SearchClient
# from azure.core.credentials import AzureKeyCredential
# from app.config import settings


# search_client = SearchClient(
#     endpoint=settings.AZURE_SEARCH_ENDPOINT,
#     index_name=settings.AZURE_SEARCH_INDEX,
#     credential=AzureKeyCredential(settings.AZURE_SEARCH_KEY)
# )

# def retrieve_from_index(query: str, top_k: int = 5):
#     results = search_client.search(
#         search_text=query,
#         top=top_k
#     )

#     docs = []

#     for r in results:
#         texto = ""

#         # 1️⃣ Casos Fabric / CSJ
#         if r.get("TEXTOPROVIDENCIA"):
#             texto = r["TEXTOPROVIDENCIA"]

#         # 2️⃣ Casos documentos cargados manualmente
#         elif r.get("content"):
#             texto = r["content"]

#         # 3️⃣ Descriptores (lista → string)
#         elif r.get("DescriptoresTesis"):
#             if isinstance(r["DescriptoresTesis"], list):
#                 texto = "\n".join(r["DescriptoresTesis"])
#             else:
#                 texto = r["DescriptoresTesis"]

#         # 4️⃣ Fallback
#         else:
#             texto = ""

#         docs.append({
#             "id": r.get("id"),
#             "texto": texto,
#             "score": r.get("@search.score"),
#             "filename": r.get("filename", "")
#         })

#     return docs


# from azure.search.documents import SearchClient
# from azure.core.credentials import AzureKeyCredential
# from app.config import settings

# search_client = SearchClient(
#     endpoint=settings.AZURE_SEARCH_ENDPOINT,
#     index_name=settings.AZURE_SEARCH_INDEX,
#     credential=AzureKeyCredential(settings.AZURE_SEARCH_KEY),
# )

# def retrieve_from_index(query: str, top_k: int = 5):
#     results = search_client.search(search_text=query, top=top_k)

#     docs = []
#     for r in results:
#         docs.append({
#             "id": r.get("id"),
#             "texto": r.get("TEXTOPROVIDENCIA", ""),
#             "problema": r.get("ProblemaJuridico", ""),
#             "decision": r.get("DECISION", "")
#         })

#     return docs

