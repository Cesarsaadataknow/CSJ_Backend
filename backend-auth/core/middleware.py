from fastapi import HTTPException, status, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from typing import List, Optional
from jose import jwt
import httpx
import logging
from core.config import Settings

logger = logging.getLogger("middleware")
logging.basicConfig(level=logging.INFO)

class User(BaseModel):
    name: Optional[str]
    email: Optional[str]
    roles: List[str] = []
    @classmethod
    def from_payload(cls, payload: dict) -> "User":
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
        
class AuthManager:
    def __init__(self, auth_cfg: Settings.Auth):
        self._cfg = auth_cfg
        self._provider_cfg = None
        self._jwks = None
        self._issuer = None
        self._audience = auth_cfg.client_id

    async def _fetch_provider_cfg(self):
        if not self._provider_cfg:
            async with httpx.AsyncClient() as client:
                r = await client.get(self._cfg.oidc_metadata_url)
                r.raise_for_status()
                self._provider_cfg = r.json()
                self._issuer = self._provider_cfg["issuer"]
                logger.info(f"[AUTH] Issuer: {self._issuer}")
        return self._provider_cfg

    async def _fetch_jwks(self):
        if not self._jwks:
            cfg = await self._fetch_provider_cfg()
            async with httpx.AsyncClient() as client:
                r = await client.get(cfg["jwks_uri"])
                r.raise_for_status()
                self._jwks = r.json()
                logger.info(f"[AUTH] JWKS keys: {len(self._jwks.get('keys', []))}")
        return self._jwks

    async def _decode_token(self, token: str) -> dict:
        jwks = await self._fetch_jwks()
        try:
            return jwt.decode(
                token,
                jwks,
                algorithms=["RS256"],
                issuer=self._issuer,
                audience=self._audience,
            )
        except jwt.ExpiredSignatureError:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token expirado")
        except jwt.JWTClaimsError as e:
            logger.warning(f"[AUTH] Claims inválidos: {e}")
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Claims inválidos")
        except jwt.JWTError as e:
            logger.error(f"[AUTH] Error validando token: {e}")
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token inválido")

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
        Permite usar AuthManager como dependencia:
            user: User = Depends(auth_manager)
        """
        return await self.decode_user(credentials.credentials)

    def inspect_token(self, token: str) -> dict:
        # Para debugging: claims sin verificar firma
        return jwt.get_unverified_claims(token)