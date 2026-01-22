from dotenv import load_dotenv, find_dotenv
from msal import ConfidentialClientApplication
import os

load_dotenv(find_dotenv())

class Settings():

    class Auth():
        def __init__(self):
            client_secret: str = os.getenv("CLIENT_SECRET")
            tenant_id: str = os.getenv("TENANT_ID")
            authority: str = f"https://login.microsoftonline.com/{tenant_id}"
            self.client_id: str = os.getenv("CLIENT_ID")
            self.redirect_uri: str = os.getenv("REDIRECT_URI")
            self.scopes_api: list[str] = [f"api://{self.client_id}/chat_access"]
            self.oidc_metadata_url: str = (
                f"https://login.microsoftonline.com/{tenant_id}"
                "/v2.0/.well-known/openid-configuration"
            )
            self.client_instance: ConfidentialClientApplication = ConfidentialClientApplication(
                client_id=self.client_id,
                client_credential=client_secret,
                authority=authority
            )

    class AIServices():
        def __init__(self):
            self.azure_openai_api_key: str = os.getenv("AZURE_OPENAI_API_KEY")
            self.openai_api_version: str = os.getenv("OPENAI_API_VERSION")
            self.azure_openai_endpoint: str = os.getenv("AZURE_OPENAI_ENDPOINT")
            self.model_gpt4o_name: str = os.getenv("MODEL_GPT4o_NAME")
            self.model_o1_mini_name: str = os.getenv("MODEL_O1_MINI_NAME", "o1-mini")
            self.reasoning_effort: str = os.getenv("REASONING_EFFORT","low")
            self.model_embeddings_name: str = os.getenv("EMBEDDING_NAME")
            self.azure_search_endpoint: str = os.getenv("AZURE_AI_SEARCH_ENDPOINT")
            self.azure_search_key: str = os.getenv("AZURE_AI_SEARCH_API_KEY")
            self.document_intelligence_endpoint: str = os.getenv("AZURE_FORM_RECOGNIZER_ENDPOINT")
            self.document_intelligence_key: str = os.getenv("AZURE_FORM_RECOGNIZER_API_KEY")
            self.document_intelligence_api_version: str = os.getenv("AZURE_FORM_RECOGNIZER_API_VERSION")
            self.tavily_api_key: str = os.getenv("TAVILY_API_KEY")

    class DBServices():
        def __init__(self):
            self.azure_cosmos_db_api_key: str = os.getenv("AZURE_COSMOSDB_KEY")
            self.azure_cosmos_db_endpoint: str = os.getenv("AZURE_COSMOSDB_ENDPOINT")
            self.azure_cosmos_db_name: str = os.getenv("AZURE_COSMOSDB_NAME")
            self.azure_cosmos_db_container_name: str = os.getenv("AZURE_COSMOSDB_CONTAINER_NAME")
            self.azure_cosmos_db_container_name_message_pairs: str = os.getenv("AZURE_COSMOSDB_CONTAINER_NAME_MESSAGE_PAIRS")

    def __init__(self):
        self.app_name: str = "SoftIAService"
        self.admin_email: str = "admin@example.com"
        self.auth: Settings.Auth = Settings.Auth()
        self.ai_services: Settings.AIServices = Settings.AIServices()
        self.db_services: Settings.DBServices = Settings.DBServices()

settings = Settings()