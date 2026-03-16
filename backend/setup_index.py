from __future__ import annotations

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
    SemanticConfiguration,
    SemanticPrioritizedFields,
    SemanticField,
    SemanticSearch,
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
        # =========================
        # CLAVES / FILTROS
        # =========================
        SimpleField(
            name="id",
            type=SearchFieldDataType.String,
            key=True,
            filterable=True,
        ),
        SimpleField(
            name="user_id",
            type=SearchFieldDataType.String,
            filterable=True,
        ),
        SimpleField(
            name="session_id",
            type=SearchFieldDataType.String,
            filterable=True,
        ),
        SimpleField(
            name="file_id",
            type=SearchFieldDataType.String,
            filterable=True,
        ),

        # =========================
        # METADATOS BASE
        # =========================
        SearchableField(
            name="file_name",
            type=SearchFieldDataType.String,
            filterable=True,
            sortable=True,
        ),
        SimpleField(
            name="chunk_id",
            type=SearchFieldDataType.Int32,
            filterable=True,
            sortable=True,
        ),
        SimpleField(
            name="page_number",
            type=SearchFieldDataType.Int32,
            filterable=True,
            sortable=True,
        ),

        # =========================
        # CONTENIDO
        # =========================
        SearchableField(
            name="content",
            type=SearchFieldDataType.String,
        ),
        SearchableField(
            name="page_context_preview",
            type=SearchFieldDataType.String,
        ),
        SearchableField(
            name="ai_reason",
            type=SearchFieldDataType.String,
            filterable=True,
        ),

        # =========================
        # FLAGS
        # =========================
        SimpleField(
            name="needs_ai",
            type=SearchFieldDataType.Boolean,
            filterable=True,
        ),
        SimpleField(
            name="has_visual_description",
            type=SearchFieldDataType.Boolean,
            filterable=True,
        ),
        SimpleField(
            name="has_figures",
            type=SearchFieldDataType.Boolean,
            filterable=True,
        ),
        SimpleField(
            name="figures_count",
            type=SearchFieldDataType.Int32,
            filterable=True,
            sortable=True,
        ),
        SimpleField(
            name="tables_count",
            type=SearchFieldDataType.Int32,
            filterable=True,
            sortable=True,
        ),
        SimpleField(
            name="has_complex_table",
            type=SearchFieldDataType.Boolean,
            filterable=True,
        ),
        SimpleField(
            name="tables_marked_for_ai",
            type=SearchFieldDataType.Boolean,
            filterable=True,
        ),

        # =========================
        # VECTOR
        # =========================
        SearchField(
            name="content_vector",
            type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
            searchable=True,
            vector_search_dimensions=3072,
            vector_search_profile_name="vs-profile",
        ),

        # =========================
        # FECHA
        # =========================
        SimpleField(
            name="created_at",
            type=SearchFieldDataType.DateTimeOffset,
            filterable=True,
            sortable=True,
        ),
    ]

    vector_search = VectorSearch(
        algorithms=[
            HnswAlgorithmConfiguration(name="hnsw-algo")
        ],
        profiles=[
            VectorSearchProfile(
                name="vs-profile",
                algorithm_configuration_name="hnsw-algo",
            )
        ],
    )

    semantic_search = SemanticSearch(
        configurations=[
            SemanticConfiguration(
                name="semantic-config-docs",
                prioritized_fields=SemanticPrioritizedFields(
                    title_field=SemanticField(field_name="file_name"),
                    content_fields=[
                        SemanticField(field_name="content"),
                        SemanticField(field_name="page_context_preview"),
                        SemanticField(field_name="ai_reason"),
                    ],
                ),
            )
        ]
    )

    index = SearchIndex(
        name=settings.AZURE_SEARCH_INDEX,
        fields=fields,
        vector_search=vector_search,
        semantic_search=semantic_search,
    )

    # borrar si existe
    try:
        print("Intentando borrar índice si existe...")
        client.delete_index(settings.AZURE_SEARCH_INDEX)
        print("Índice borrado.")
    except Exception as e:
        print("No se pudo borrar:", repr(e))

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