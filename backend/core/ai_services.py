from app.config import settings
from openai import AzureOpenAI

class AIServices:

    @staticmethod
    def chat_client():
        return AzureOpenAI(
            api_key=settings.AZURE_OPENAI_KEY,
            azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
            api_version="2024-02-15-preview"
        )



# from openai import AzureOpenAI
# from app.config import settings

# class AIServices:

#     _client = None
#     _embedding_client = None

#     @classmethod
#     def chat_client(cls):
#         if cls._client is None:
#             cls._client = AzureOpenAI(
#                 api_key=settings.ai_services.openai_key,
#                 api_version="2024-02-01",
#                 azure_endpoint=settings.ai_services.openai_endpoint
#             )
#         return cls._client

#     @classmethod
#     def embed_query(cls, text: str) -> list[float]:
#         if cls._embedding_client is None:
#             cls._embedding_client = AzureOpenAI(
#                 api_key=settings.ai_services.openai_key,
#                 api_version="2024-02-01",
#                 azure_endpoint=settings.ai_services.openai_endpoint
#             )

#         emb = cls._embedding_client.embeddings.create(
#             model=settings.ai_services.embedding_deployment,
#             input=text
#         )
#         return emb.data[0].embedding
