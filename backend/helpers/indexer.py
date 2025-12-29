from azure.search.documents import SearchClient
from azure.core.credentials import AzureKeyCredential
from app.config import settings
import uuid

search_client = SearchClient(
    endpoint=settings.AZURE_SEARCH_ENDPOINT,
    index_name=settings.AZURE_SEARCH_INDEX,
    credential=AzureKeyCredential(settings.AZURE_SEARCH_KEY)
)

import uuid

def index_document(text: str):
    doc = {
        "id": str(uuid.uuid4()),
        "TEXTOPROVIDENCIA": text
    }

    search_client.upload_documents([doc])

