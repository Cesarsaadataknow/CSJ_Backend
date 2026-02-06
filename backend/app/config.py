from pathlib import Path
from msal import ConfidentialClientApplication
import os
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")



class Settings:

    def __init__(self):
        """
        Inicializa la configuración principal y todas las subconfiguraciones.
        """
        #self.app_name: str = "GPTCorporativoService"
        #self.admin_email: str = "admin@example.com"
        self.auth: Settings.Auth = Settings.Auth()

    # -------------------------------------------------------------------------
    # region           SUBCLASE: CONFIGURACIÓN DE AUTENTICACIÓN
    # -------------------------------------------------------------------------
    class Auth():
        """
        Configuración específica para autenticación con Microsoft Entra ID.
        Incluye client ID, secret, tenant ID, scopes y cliente MSAL.
        """
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
    # endregion


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
    AZURE_SEARCH_INDEX_FABRIC = os.getenv("AZURE_SEARCH_INDEX_FABRIC")

    # Cosmos DB
    AZURE_COSMOSDB_KEY= os.getenv("AZURE_COSMOSDB_KEY")
    AZURE_COSMOSDB_ENDPOINT= os.getenv("AZURE_COSMOSDB_ENDPOINT")
    AZURE_COSMOSDB_NAME= os.getenv("AZURE_COSMOSDB_NAME")
    AZURE_COSMOSDB_CONTAINER_NAME_SESSION= os.getenv("AZURE_COSMOSDB_CONTAINER_NAME_SESSION")
    AZURE_COSMOSDB_CONTAINER_NAME_MGS= os.getenv("AZURE_COSMOSDB_CONTAINER_NAME_MGS")
    AZURE_COSMOSDB_CONTAINER_NAME_DOCS= os.getenv("AZURE_COSMOSDB_CONTAINER_NAME_DOCS")

    # Document Intelligence
    AZURE_FORM_RECOGNIZER_ENDPOINT=os.getenv("AZURE_FORM_RECOGNIZER_ENDPOINT")
    AZURE_FORM_RECOGNIZER_API_KEY=os.getenv("AZURE_FORM_RECOGNIZER_API_KEY")

    #Rutas
    DOCX_TEMPLATE_PATH = os.getenv("DOCX_TEMPLATE_PATH")


    def validate(self):
        missing = [k for k, v in self.__dict__.items() if v is None]
        if missing:
            raise RuntimeError(f"Variables de entorno faltantes: {missing}")

settings = Settings()
settings.validate()