from azure.search.documents import SearchClient
from azure.search.documents.models import VectorizedQuery
from azure.core.credentials import AzureKeyCredential
from core.config import settings
from core.ai_services import AIServices

search_client = SearchClient(
    endpoint=settings.ai_services.search_endpoint,
    index_name=settings.ai_services.search_index,
    credential=AzureKeyCredential(settings.ai_services.search_key)
)

async def retrieve_from_index(query: str, top_k: int = 6) -> list[dict]:

    query_vector = AIServices.embed_query(query)

    vector_query = VectorizedQuery(
        vector=query_vector,
        k_nearest_neighbors=top_k,
        fields="texto_vector"
    )

    results = search_client.search(
        search_text=query,
        vector_queries=[vector_query],
        query_type="semantic",
        semantic_configuration_name="semantic-config",
        top=top_k
    )

    docs = []
    for r in results:
        docs.append({
            "id": r["id"],
            "texto": r["TEXTOPROVIDENCIA"],
            "NaturalezaProceso": r.get("NaturalezaProceso"),
            "claseProceso": r.get("claseProceso"),
            "ACTOR": r.get("ACTOR"),
            "DEMANDADO": r.get("DEMANDADO"),
            "ProblemaJuridico": r.get("ProblemaJuridico"),
        })

    return docs
