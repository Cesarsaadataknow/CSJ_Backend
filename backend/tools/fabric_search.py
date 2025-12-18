from azure.search.documents import SearchClient
from azure.core.credentials import AzureKeyCredential
from app.config import settings

client = SearchClient(
    endpoint=settings.FABRIC_SEARCH_ENDPOINT,
    index_name=settings.FABRIC_SEARCH_INDEX,
    credential=AzureKeyCredential(settings.FABRIC_SEARCH_KEY),
)

def search_jurisprudencia(query: str, top_k: int = 5) -> str:
    results = client.search(
        search_text=query,
        query_type="semantic",
        semantic_configuration_name="semantic-config",
        top=top_k,
        search_fields=[
            "TEXTOPROVIDENCIA",
            "ProblemaJuridico",
            "DescriptoresTesis",
            "DECISION"
        ],
        select=[
            "TEXTOPROVIDENCIA",
            "NaturalezaProceso",
            "claseProceso",
            "ACTOR",
            "DEMANDADO",
            "DECISION",
            "ProblemaJuridico",
            "DescriptoresTesis"
        ]
    )

    context = []
    for r in results:
        context.append(f"""
Sentencia:
Naturaleza: {r.get('NaturalezaProceso')}
Clase: {r.get('claseProceso')}
Actor: {r.get('ACTOR')}
Demandado: {r.get('DEMANDADO')}
Problema Jurídico: {r.get('ProblemaJuridico')}
Decisión: {r.get('DECISION')}
Descriptores: {", ".join(r.get("DescriptoresTesis", []))}

Texto:
{r.get("TEXTOPROVIDENCIA")}
""")

    return "\n\n---\n\n".join(context)
