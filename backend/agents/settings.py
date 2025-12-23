from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Azure OpenAI
    AZURE_OPENAI_ENDPOINT: str
    AZURE_OPENAI_KEY: str
    AZURE_OPENAI_CHAT_DEPLOYMENT: str
    AZURE_OPENAI_EMBEDDING_DEPLOYMENT: str

    # Azure AI Search
    AZURE_SEARCH_ENDPOINT: str
    AZURE_SEARCH_KEY: str
    AZURE_SEARCH_INDEX: str

    class Config:
        env_file = ".env"


settings = Settings()
