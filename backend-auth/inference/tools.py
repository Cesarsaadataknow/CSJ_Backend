
from typing import Any, Optional, cast
from langchain_community.tools.tavily_search import TavilySearchResults
from core.ai_services import AIServices

# Importa tu settings con la clave ya cargada
from core.config import settings

ai_search_service = AIServices().AzureAiSearch()

async def search_tool(query: str) -> Optional[list[dict[str, Any]]]:
    """
    Query a search engine (TavilySearchResults) usando la key de config.
    """
    print(f"\033[92msearch_tool activada | query: {query}\033[0m")
    wrapped = TavilySearchResults(
        max_results=5,
        tavily_api_key=settings.ai_services.tavily_api_key  
    )
    result = await wrapped.ainvoke({"query": query})
    return cast(list[dict[str, Any]], result)

async def retrieval_tool(query: str, conversation_id:str ) -> Optional[list[dict[str, Any]]]:
    """
    Hace
    """
    print(f"\033[92mretrieval_tool activada | query: {query} | conversation_id: {conversation_id}\033[0m")

    documents = await ai_search_service.search_documents_in_index(
        index_name="chat-index",
        search_text=query,
        conversation_id=conversation_id
    )
    print(f"\033[92m{len(documents)} Documentos Recuperados\033[0m")
    if len(documents) == 0:
        return []
    
    docs = [
        {"file_name": d["file_name"], "page_content": d["page_content"]}
        for d in documents
    ]


    return cast(list[dict[str, Any]], docs)


