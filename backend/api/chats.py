
# -----------------------------------------------------------------------------
# region           IMPORTACIONES
# -----------------------------------------------------------------------------
import os
import json
import base64
from typing import Optional, List
from core.ai_services import AIServices
from fastapi.responses import Response
from helpers.orchestrator import Orchestrator  
from core.middleware import AuthManager, User
from datetime import datetime
from azure.cosmos import exceptions
from fastapi import APIRouter, UploadFile, File, Form, Depends, Query, HTTPException, Path
from app.config import settings
from helpers.schema_http import (
    ChatJSONRequest, ResponseHTTPSessions, 
    ResponseHTTPOneSession,ResponseHTTPDelete, Message
)
# endregion

# -----------------------------------------------------------------------------
# region           ROUTERS DE CONEXION
# -----------------------------------------------------------------------------
chat_router = APIRouter(prefix="/api", tags=["chat"])
download_router = APIRouter(prefix="/api", tags=["chat-download"])
# endregion

# -----------------------------------------------------------------------------
# region         INICIALIZACIÓN Y CONFIGURACIÓN
# -----------------------------------------------------------------------------
auth_manager = AuthManager(settings.auth)
cosmos = AIServices.AzureCosmosDB()
orchestrator = Orchestrator()
# endregion

# -----------------------------------------------------------------------------
# region           TIPO DE ARCHIVOS PERMITIDO
# -----------------------------------------------------------------------------
ALLOWED_MIME_TYPES = {
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}

ALLOWED_EXTENSIONS = {".pdf", ".doc", ".docx"}
# endregion

# -----------------------------------------------------------------------------
# region           ENDPOINT: PREGUNTA GENERAL DE USUSARIO
# -----------------------------------------------------------------------------
def _extract_tool_json(reply_text: str) -> dict | None:
    """
    Intenta sacar el JSON devuelto por tool_word aunque venga mezclado con texto.
    """
    if not reply_text:
        return None

    txt = reply_text.strip()

    # 1) Caso ideal: es JSON puro
    try:
        obj = json.loads(txt)
        return obj if isinstance(obj, dict) else None
    except Exception:
        pass

    # 2) Busca un bloque JSON dentro del texto (del primer { al último })
    start = txt.find("{")
    end = txt.rfind("}")
    if start != -1 and end != -1 and end > start:
        candidate = txt[start:end+1]
        try:
            obj = json.loads(candidate)
            return obj if isinstance(obj, dict) else None
        except Exception:
            pass

    # 3) Fallback: saca doc_id por regex aunque no haya JSON válido
    m = re.search(r'"doc_id"\s*:\s*"([^"]+)"', txt)
    if m:
        return {"doc_id": m.group(1)}

    return None


@chat_router.post("/ask")
async def ask(
    question: str,
    session_id: str | None = None,
    user: User = Depends(auth_manager),
):
    if not question or not question.strip():
        raise HTTPException(status_code=400, detail="question es requerida.")

    user_id = getattr(user, "email", None) or getattr(user, "id", None) or getattr(user, "user_id", None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Usuario no autenticado.")

    res = await orchestrator.ejecutar_agente(
        mensaje_usuario=question.strip(),
        user_id=user_id,
        session_id=session_id,
        files=None,
    )

    reply_text = res.get("reply_text", "") or ""

    tool_payload = _extract_tool_json(reply_text)

    # ✅ Si el tool devolvió doc_id, lo retornamos separado para el front
    if tool_payload and tool_payload.get("doc_id"):
        return {
            "answer": tool_payload.get("message") or "Documento generado.",
            "session_id": res.get("session_id"),
            "doc_id": tool_payload.get("doc_id"),
            "download_url": tool_payload.get("download_url"),
            "file_name": tool_payload.get("file_name"),
            "ok": tool_payload.get("ok", True),
        }

    # ✅ Respuesta normal
    return {
        "answer": reply_text,
        "session_id": res.get("session_id"),
    }
# endregion

# -----------------------------------------------------------------------------
# region           ENDPOINT: CARGA DE ARCHIVOS
# -----------------------------------------------------------------------------
@chat_router.post("/upload")
async def upload(
    session_id: Optional[str] = None,
    files: List[UploadFile] = File(...),
    user: User = Depends(auth_manager),
):
    user_id = getattr(user, "email", None) or getattr(user, "id", None) or getattr(user, "user_id", None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Usuario no autenticado.")

    if not files:
        raise HTTPException(status_code=400, detail="Se requiere al menos un archivo.")

    for f in files:
        filename = f.filename or ""
        ext = os.path.splitext(filename.lower())[1]
        ctype = (f.content_type or "").lower()

        if ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=415,
                detail=f"Archivo no permitido: {filename}. Solo se aceptan PDF y Word (.doc, .docx).",
            )

        # OJO: a veces ctype llega vacío, por eso solo validamos si viene
        if ctype and ctype not in ALLOWED_MIME_TYPES:
            raise HTTPException(
                status_code=415,
                detail=f"Tipo de archivo no permitido: {filename} ({f.content_type}).",
            )

    res = await orchestrator.ejecutar_agente(
        mensaje_usuario="",    
        user_id=user_id,
        session_id=session_id,
        files=files,
    )
    return res
# endregion

# -----------------------------------------------------------------------------
# region           ENDPOINT: DESCARGA DE DOCUMENTOS
# -----------------------------------------------------------------------------
@download_router.get("/download/doc/{doc_id}")
async def download_docx_by_id(doc_id: str, user: User = Depends(auth_manager)):
    user_id = user.email 
    item = orchestrator.cosmosdb.get_generated_doc_by_id(doc_id=doc_id)
    if not item:
        raise HTTPException(404, "Documento no encontrado.")

    if item.get("user_id") != user_id:
        raise HTTPException(403, "No tienes acceso a este documento.")

    b64 = item.get("docx_b64")
    if not b64:
        raise HTTPException(404, "Documento sin contenido.")

    file_bytes = base64.b64decode(b64)
    filename = item.get("file_name") or f"{doc_id}.docx"

    return Response(
        content=file_bytes,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
# endregion

# -----------------------------------------------------------------------------
# region           ENDPOINT: OBTENER SESIONES DE USUARIO
# -----------------------------------------------------------------------------
@chat_router.get("/sessions", response_model=ResponseHTTPSessions)
async def read_sessions(user: User = Depends(auth_manager)):
    user_id = user.email
    sessions = cosmos.get_user_sessions(user_id)  
    if not sessions:
        sessions = []
    clean = [
        {
            "id": s["id"],
            "name_session": s.get("name_session", "Sesión"),
            "updated_at": s.get("updated_at"),
            "fecha_creacion": s.get("fecha_creacion"),
            "channel": s.get("channel", "web"),
        }
        for s in sessions
    ]
    return {"sessions": clean}
# endregion

# -----------------------------------------------------------------------------
# region         ENDPOINT: OBTENER UNA SESIÓN ESPECÍFICA
# -----------------------------------------------------------------------------
@chat_router.get("/get_one_session", response_model=ResponseHTTPOneSession)
async def read_one_session(conversation_id: str = Query(...), user: User = Depends(auth_manager)):

    # Validación: la sesión debe pertenecer al usuario
    try:
        session = cosmos.sessions_container.read_item(item=conversation_id, partition_key=conversation_id)
    except exceptions.CosmosResourceNotFoundError:
        return ResponseHTTPOneSession(conversation_id=conversation_id, conversation_name="", messages=[])

    if session.get("user_id") != user.email:
        raise HTTPException(status_code=403, detail="No autorizado para ver esta sesión.")

    raw_msgs = cosmos.get_session_messages(conversation_id)  # sin await

    mapped: list[Message] = []
    for m in raw_msgs:
        created = m.get("created_at")
        created_dt = datetime.fromisoformat(created.replace("Z", "+00:00")) if isinstance(created, str) else created

        extra = m.get("extra") or {}
        files = extra.get("uploaded_files")

        # Mensaje usuario
        mapped.append(Message(
            id=f'{m["id"]}-q',
            role="user",
            content=m.get("UserQuestion", ""),
            created_at=created_dt,
            rate=m.get("rate"),
            files=files
        ))

        # Mensaje asistente
        mapped.append(Message(
            id=f'{m["id"]}-a',
            role="assistant",
            content=str(m.get("IAResponse", "")),
            created_at=created_dt,
            rate=m.get("rate"),
            files=None
        ))

    return ResponseHTTPOneSession(
        conversation_id=conversation_id,
        conversation_name=session.get("name_session", ""),
        messages=mapped
    )
# endregion

# -----------------------------------------------------------------------------
# region         ENDPOINT: ELIMINAR UNA SESIÓN ESPECÍFICA
# -----------------------------------------------------------------------------
@chat_router.delete("/delete_one_session/{conversation_id}", response_model=ResponseHTTPDelete)
async def delete_one_session(conversation_id: str = Path(...), user: User = Depends(auth_manager)):

    # Validación: sesión del usuario
    try:
        session = cosmos.sessions_container.read_item(item=conversation_id, partition_key=conversation_id)
    except exceptions.CosmosResourceNotFoundError:
        raise HTTPException(status_code=404, detail="Sesión no encontrada.")

    if session.get("user_id") != user.email:
        raise HTTPException(status_code=403, detail="No autorizado para eliminar esta sesión.")

    cosmos.delete_session(conversation_id)

    return {
        "message": f"Sesión {conversation_id} eliminada correctamente.",
        "deleted_count": 1
    }
# endregion