"""
===============================================================================
DESCRIPCIÓN: Define los esquemas Pydantic para las solicitudes y respuestas HTTP.
             Incluye modelos para:
             1. Chat (mensajes y respuestas)
             2. Votación de respuestas
             3. Sesiones de conversación
             4. Eliminación de sesiones
===============================================================================
"""

# -----------------------------------------------------------------------------
# region                           IMPORTS
# -----------------------------------------------------------------------------
from pydantic import BaseModel
from typing import Optional, Literal, List
from datetime import datetime
# endregion


# -----------------------------------------------------------------------------
# region               ESQUEMAS DE CHAT (MENSAJES)
# -----------------------------------------------------------------------------

class ChatJSONRequest(BaseModel):
    question: str
    session_id: str | None = None
# endregion

# -----------------------------------------------------------------------------
# region               ESQUEMAS DE SESIONES
# -----------------------------------------------------------------------------

class ResponseHTTPSessions(BaseModel):
    """Respuesta con lista de sesiones de conversación."""
    sessions: list
# endregion

# -----------------------------------------------------------------------------
# region               ESQUEMAS DE UNA SESIÓN ESPECÍFICA
# -----------------------------------------------------------------------------
class RequestHTTPOneSession(BaseModel):
    """Solicitud para obtener una sesión específica."""
    conversation_id: str

class Message(BaseModel):
    """Modelo de mensaje individual dentro de una conversación."""
    id: str 
    role: str 
    content: str 
    created_at: datetime
    rate: Optional[Literal[None, 0, 1, 2]] = None
    files: Optional[List[str]] = None

class ResponseHTTPOneSession(BaseModel):
    """Respuesta con los detalles de una sesión de conversación."""
    conversation_id: str
    conversation_name: str
    messages: list[Message]
# endregion

# -----------------------------------------------------------------------------
# region               ESQUEMA DE ELIMINACIÓN
# -----------------------------------------------------------------------------
class ResponseHTTPDelete(BaseModel):
    """Respuesta después de eliminar una sesión."""
    message: str
    deleted_count: int
# endregion