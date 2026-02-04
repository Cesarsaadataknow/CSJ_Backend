from azure.search.documents import SearchClient
from azure.core.credentials import AzureKeyCredential
from app.config import settings
from datetime import datetime
import uuid


search_client = SearchClient(
    endpoint=settings.AZURE_SEARCH_ENDPOINT,
    index_name=settings.AZURE_SEARCH_DOCS_INDEX,
    credential=AzureKeyCredential(settings.AZURE_SEARCH_KEY),
)


def index_document_chunks(chunks: list[str], filename: str):
    docs = []
    base_id = str(uuid.uuid4())

    for i, chunk in enumerate(chunks):
        docs.append({
            "id": f"{base_id}_{i}",
            "content": chunk,
            "filename": filename,
            "uploaded_at": datetime.utcnow().isoformat(),
        })

    search_client.upload_documents(docs)
    return base_id



# from azure.search.documents import SearchClient
# from azure.core.credentials import AzureKeyCredential
# from app.config import settings
# import uuid

# search_client = SearchClient(
#     endpoint=settings.AZURE_SEARCH_ENDPOINT,
#     index_name=settings.AZURE_SEARCH_INDEX,
#     credential=AzureKeyCredential(settings.AZURE_SEARCH_KEY)
# )

# import uuid

# def index_document(text: str):
#     doc = {
#         "id": str(uuid.uuid4()),
#         "TEXTOPROVIDENCIA": text
#     }

#     search_client.upload_documents([doc])

