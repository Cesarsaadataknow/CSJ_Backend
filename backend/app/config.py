from pathlib import Path
import os
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

class Settings:
    # Azure OpenAI
    AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
    AZURE_OPENAI_KEY = os.getenv("AZURE_OPENAI_KEY")
    AZURE_OPENAI_CHAT_DEPLOYMENT = os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT")
    AZURE_OPENAI_EMBEDDING_DEPLOYMENT = os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT")
    AZURE_OPENAI_OPENAI_VERSION=os.getenv("AZURE_OPENAI_OPENAI_VERSION")

    # Azure AI Search
    AZURE_SEARCH_ENDPOINT = os.getenv("AZURE_SEARCH_ENDPOINT")
    AZURE_SEARCH_KEY = os.getenv("AZURE_SEARCH_KEY")
    AZURE_SEARCH_INDEX = os.getenv("AZURE_SEARCH_INDEX")

    # Cosmos DB
    AZURE_COSMOSDB_KEY= os.getenv("AZURE_COSMOSDB_KEY")
    AZURE_COSMOSDB_ENDPOINT= os.getenv("AZURE_COSMOSDB_ENDPOINT")
    AZURE_COSMOSDB_NAME= os.getenv("AZURE_COSMOSDB_NAME")
    AZURE_COSMOSDB_CONTAINER_NAME_SESSION= os.getenv("AZURE_COSMOSDB_CONTAINER_NAME_SESSION")
    AZURE_COSMOSDB_CONTAINER_NAME_MGS= os.getenv("AZURE_COSMOSDB_CONTAINER_NAME_MGS")


    def validate(self):
        missing = [k for k, v in self.__dict__.items() if v is None]
        if missing:
            raise RuntimeError(f"Variables de entorno faltantes: {missing}")

settings = Settings()
settings.validate()