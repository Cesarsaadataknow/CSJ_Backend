"""
===============================================================================
DESCRIPCIÓN: Contiene los endpoints de autenticación OAuth2 con Microsoft Entra ID (Azure AD):
             1. Login: Redirecciona al portal de autenticación de Microsoft
             2. Token: Intercambia código de autorización por token de acceso
             3. Test: Endpoint de prueba para verificar funcionamiento
===============================================================================
"""

# -----------------------------------------------------------------------------
# region                           IMPORTS
# -----------------------------------------------------------------------------
from fastapi import Request, APIRouter
from fastapi.responses import RedirectResponse, JSONResponse
import logging
from core.middleware import AuthManager
from app.config import settings
# endregion

# -----------------------------------------------------------------------------
# region               INICIALIZACIÓN Y CONFIGURACIÓN
# -----------------------------------------------------------------------------
router = APIRouter()
settings_auth = settings.auth
auth_manager = AuthManager(settings_auth)
# endregion

# -----------------------------------------------------------------------------
# region               ENDPOINT: INICIAR LOGIN
# -----------------------------------------------------------------------------
@router.get("/login")
def login(request: Request):
    """
    Endpoint que redirige al usuario al portal de autenticación de Microsoft.
    Soporta parámetro 'prompt' para forzar reautenticación.
    """
    prompt = request.query_params.get('prompt', None)
    if prompt:
        redirect_uri = settings_auth.client_instance.get_authorization_request_url(settings_auth.scopes_api, prompt='login')
    else:
        redirect_uri = settings_auth.client_instance.get_authorization_request_url(settings_auth.scopes_api)
    return RedirectResponse(redirect_uri)
# endregion

# -----------------------------------------------------------------------------
# region           ENDPOINT: INTERCAMBIAR CÓDIGO POR TOKEN
# -----------------------------------------------------------------------------
@router.get("/token")
async def auth_token(request: Request):
    """
    Endpoint que intercambia un código de autorización por un token de acceso.
    Retorna el token junto con información del usuario (nombre y permisos).
    """
    code = request.query_params.get("code")
    if not code:
        return JSONResponse({"error": "No authorization code"}, status_code=400)

    try:
        token_result = settings_auth.client_instance.acquire_token_by_authorization_code(
            code=code,
            scopes=settings_auth.scopes_api,
            redirect_uri=settings_auth.redirect_uri
        )
    except Exception as e:
        return JSONResponse({"error": f"Token exchange failed: {str(e)}"}, status_code=400)

    if "access_token" not in token_result:
        return JSONResponse({"error": token_result.get("error_description", "No token")}, status_code=400)

    access_token = token_result["access_token"]
    logging.info(f"Access Token: {access_token}")
    user = await auth_manager.decode_user(access_token)
    return {
        "access_token": access_token,
        "name": user.name,
        "permissions": user.roles
    }
# endregion

# -----------------------------------------------------------------------------
# region               ENDPOINT: PRUEBA DE FUNCIONAMIENTO
# -----------------------------------------------------------------------------
@router.get("/test")
async def root():
    """
    Endpoint de prueba para verificar que el servicio de autenticación está funcionando.
    """
    return JSONResponse(content={"message": "ok"}, status_code=200)
# endregion