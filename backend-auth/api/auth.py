from fastapi import Request, APIRouter
from fastapi.responses import RedirectResponse, JSONResponse
import logging

from core.middleware import AuthManager
from core.config import settings

router = APIRouter()
settings_auth = settings.auth
auth_manager = AuthManager(settings_auth)

@router.get("/login")
def login(request: Request):
    prompt = request.query_params.get('prompt', None)
    if prompt:
        redirect_uri = settings_auth.client_instance.get_authorization_request_url(settings_auth.scopes_api, prompt='login')
    else:
        redirect_uri = settings_auth.client_instance.get_authorization_request_url(settings_auth.scopes_api)
    return RedirectResponse(redirect_uri)

@router.get("/token")
async def auth_token(request: Request):
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
        "permissions": user.roles,
        "email": user.email
    }
    
@router.get("/test")
async def root():
    return JSONResponse(content={"message": "ok"}, status_code=200)
