from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    SearchIndex,
    SimpleField,
    SearchableField
)
from azure.core.credentials import AzureKeyCredential
from app.config import settings


DOC_INDEX_NAME = settings.AZURE_SEARCH_DOCS_INDEX


def create_docs_index():
    client = SearchIndexClient(
        endpoint=settings.AZURE_SEARCH_ENDPOINT,
        credential=AzureKeyCredential(settings.AZURE_SEARCH_KEY),
    )

    fields = [
        SimpleField(
            name="id",
            type="Edm.String",
            key=True,
            filterable=True
        ),
        SearchableField(
            name="content",
            type="Edm.String",
            analyzer_name="es.lucene"
        ),
        SimpleField(
            name="filename",
            type="Edm.String",
            filterable=True
        ),
        SimpleField(
            name="uploaded_at",
            type="Edm.String"
        ),
    ]

    index = SearchIndex(
        name=DOC_INDEX_NAME,
        fields=fields
    )

    client.create_or_update_index(index)
    print(f"✅ Índice '{DOC_INDEX_NAME}' creado")
