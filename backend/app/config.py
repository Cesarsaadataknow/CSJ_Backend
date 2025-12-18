import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
    AZURE_OPENAI_KEY = os.getenv("AZURE_OPENAI_KEY")
    AZURE_OPENAI_DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT")
    AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION")

    FABRIC_SEARCH_ENDPOINT = os.getenv("FABRIC_SEARCH_ENDPOINT")
    FABRIC_SEARCH_KEY = os.getenv("FABRIC_SEARCH_KEY")
    FABRIC_SEARCH_INDEX = os.getenv("FABRIC_SEARCH_INDEX")

settings = Settings()
