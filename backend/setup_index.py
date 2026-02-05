# setup_index.py (en la raíz: backend/setup_index.py)
from __future__ import annotations

import sys
from azure.core.credentials import AzureKeyCredential
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    SearchIndex,
    SimpleField,
    SearchableField,
    SearchField,
    SearchFieldDataType,
    VectorSearch,
    HnswAlgorithmConfiguration,
    VectorSearchProfile,
)

from app.config import settings


def create_or_replace_index() -> None:
    print("Iniciando setup_index.py ...")
    print("SEARCH ENDPOINT:", settings.AZURE_SEARCH_ENDPOINT)
    print("INDEX NAME:", settings.AZURE_SEARCH_INDEX)

    client = SearchIndexClient(
        endpoint=settings.AZURE_SEARCH_ENDPOINT,
        credential=AzureKeyCredential(settings.AZURE_SEARCH_KEY),
    )

    fields = [
        SimpleField(name="id", type=SearchFieldDataType.String, key=True, filterable=True),

        SimpleField(name="user_id", type=SearchFieldDataType.String, filterable=True),
        SimpleField(name="session_id", type=SearchFieldDataType.String, filterable=True),
        SimpleField(name="file_id", type=SearchFieldDataType.String, filterable=True),

        SearchableField(name="file_name", type=SearchFieldDataType.String, filterable=True),
        SimpleField(name="chunk_id", type=SearchFieldDataType.Int32, filterable=True, sortable=True),

        SearchableField(name="content", type=SearchFieldDataType.String),

        SearchField(
            name="content_vector",
            type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
            searchable=True,
            vector_search_dimensions=3072,
            vector_search_profile_name="vs-profile",
        ),

        SimpleField(
            name="created_at",
            type=SearchFieldDataType.DateTimeOffset,
            filterable=True,
            sortable=True,
        ),
    ]

    vector_search = VectorSearch(
        algorithms=[HnswAlgorithmConfiguration(name="hnsw-algo")],
        profiles=[VectorSearchProfile(name="vs-profile", algorithm_configuration_name="hnsw-algo")],
    )

    index = SearchIndex(name=settings.AZURE_SEARCH_INDEX, fields=fields, vector_search=vector_search)

    # borrar si existe
    try:
        print("Intentando borrar índice si existe...")
        client.delete_index(settings.AZURE_SEARCH_INDEX)
        print("Índice borrado.")
    except Exception as e:
        print("No se pudo borrar):", repr(e))

    # crear
    print("Creando índice...")
    client.create_index(index)
    print("Índice creado OK.")


def main() -> None:
    try:
        create_or_replace_index()
    except Exception as e:
        print("ERROR:", repr(e))
        raise


if __name__ == "__main__":
    main()
