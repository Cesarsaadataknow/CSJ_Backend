"""
===============================================================================
DESCRIPCIÓN: Sistema de autenticación y autorización basado en JWT.
             Incluye:
             1. Gestor de autenticación (AuthManager)
             2. Modelo de usuario (User)
             3. Validación de tokens JWT con Microsoft Entra ID
             4. Integración como dependencia de FastAPI
===============================================================================
"""

# -----------------------------------------------------------------------------
# region                           IMPORTS
# -----------------------------------------------------------------------------
from fastapi import HTTPException, status, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from typing import List, Optional
from jose import jwt
import httpx
import logging
from app.config import Settings
# endregion

# -----------------------------------------------------------------------------
# region               CONFIGURACIÓN DE LOGGING
# -----------------------------------------------------------------------------
logger = logging.getLogger("middleware")
logging.basicConfig(level=logging.INFO)
# endregion

# -----------------------------------------------------------------------------
# region                   MODELO DE USUARIO
# -----------------------------------------------------------------------------
class User(BaseModel):
    """
    Modelo de datos para representar un usuario autenticado.
    Contiene nombre, email y roles/permissions.
    """
    name: Optional[str]
    email: Optional[str]
    roles: List[str] = []
    
    @classmethod
    def from_payload(cls, payload: dict) -> "User":
        """
        Crea una instancia de User a partir del payload del token JWT.
        Extrae el email de diferentes claims posibles.
        """
        email = (
            payload.get("preferred_username")
            or payload.get("email")
            or payload.get("upn")
            or payload.get("unique_name")
        )
        return cls(
            name=payload.get("name"),
            email=email,
            roles=payload.get("roles", []),
        )
# endregion

# -----------------------------------------------------------------------------
# region                   GESTOR DE AUTENTICACIÓN
# -----------------------------------------------------------------------------
class AuthManager:
    """
    Clase principal para gestionar la autenticación JWT.
    Se encarga de:
    - Obtener configuración del proveedor OIDC
    - Obtener claves JWKS
    - Decodificar y validar tokens
    - Extraer información del usuario
    """
    
    def __init__(self, auth_cfg: Settings.Auth):
        """
        Inicializa el gestor de autenticación con la configuración proporcionada.
        """
        self._cfg = auth_cfg
        self._provider_cfg = None
        self._jwks = None
        self._issuer = None
        self._audience = auth_cfg.client_id

    # -------------------------------------------------------------------------
    # region           MÉTODOS PRIVADOS: OBTENER CONFIGURACIÓN
    # -------------------------------------------------------------------------
    async def _fetch_provider_cfg(self):
        """
        Obtiene la configuración del proveedor OIDC desde el endpoint de metadata.
        """
        if not self._provider_cfg:
            async with httpx.AsyncClient() as client:
                r = await client.get(self._cfg.oidc_metadata_url)
                r.raise_for_status()
                self._provider_cfg = r.json()
                self._issuer = self._provider_cfg["issuer"]
                logger.info(f"[AUTH] Issuer: {self._issuer}")
        return self._provider_cfg

    async def _fetch_jwks(self):
        """
        Obtiene las claves JWKS del proveedor para validar firmas JWT.
        """
        if not self._jwks:
            cfg = await self._fetch_provider_cfg()
            async with httpx.AsyncClient() as client:
                r = await client.get(cfg["jwks_uri"])
                r.raise_for_status()
                self._jwks = r.json()
                logger.info(f"[AUTH] JWKS keys: {len(self._jwks.get('keys', []))}")
        return self._jwks

    async def _decode_token(self, token: str) -> dict:
        """
        Decodifica y valida un token JWT utilizando las claves JWKS.
        Verifica firma, issuer, audience y expiración.
        """
        jwks = await self._fetch_jwks()
        try:
            return jwt.decode(
                token,
                jwks,
                algorithms=["RS256"],
                issuer=self._issuer,
                audience=self._audience,
            )
        except jwt.ExpiredSignatureError as e:
            logger.error(f"[AUTH] Error token expirado: {e}")
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token expirado")
        except jwt.JWTClaimsError as e:
            logger.warning(f"[AUTH] Claims inválidos: {e}")
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Claims inválidos")
        except jwt.JWTError as e:
            logger.error(f"[AUTH] Error validando token: {e}")
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token inválido")
    # endregion

    # -------------------------------------------------------------------------
    # region           MÉTODOS PÚBLICOS: DECODIFICAR USUARIO
    # -------------------------------------------------------------------------
    async def decode_user(self, token: str) -> User:
        """
        Decodifica el JWT y devuelve siempre un User.
        Úsalo directamente pasando el access_token.
        """
        payload = await self._decode_token(token)
        return User.from_payload(payload)
    
    async def __call__(
        self,
        credentials: HTTPAuthorizationCredentials = Security(HTTPBearer())
    ) -> User:
        """
        Permite usar AuthManager como dependencia de FastAPI:
            user: User = Depends(auth_manager)
        """
        return await self.decode_user(credentials.credentials)

    def inspect_token(self, token: str) -> dict:
        """
        Para debugging: obtiene los claims sin verificar la firma.
        Solo para desarrollo/testing.
        """
        return jwt.get_unverified_claims(token)
    # endregion
# endregion