# -----------------------------------------------------------------------------
# region                           IMPORTS
# -----------------------------------------------------------------------------
import io
import os
import uuid
import asyncio
from fastapi import APIRouter, UploadFile, File, Form, Depends, Query, HTTPException, Path
from fastapi.responses import StreamingResponse
from datetime import datetime
from azure.cosmos import exceptions
from core.ai_services import AIServices
from core.middleware import AuthManager, User
from helpers.download_doc import OneLakeDownloader
from app.config import settings
from helpers.schema_http import (
    ChatJSONRequest, ResponseHTTPSessions, 
    ResponseHTTPOneSession,ResponseHTTPDelete, Message
)
from helpers.orchestrator import Orchestrator
# endregion

# -----------------------------------------------------------------------------
# region               INICIALIZACIÓN Y CONFIGURACIÓN
# -----------------------------------------------------------------------------
downloader = OneLakeDownloader()
orchestrator = Orchestrator()
cosmos_db = AIServices.AzureCosmosDB()
auth_manager = AuthManager(settings.auth)
chat_router = APIRouter(tags=["chat"])
download_router = APIRouter(tags=["download"])
# endregion


# -----------------------------------------------------------------------------
# region               ENDPOINT: PROCESAR MENSAJE DE CHAT
# -----------------------------------------------------------------------------
@chat_router.post("/json")
async def chat_json(payload: ChatJSONRequest, user: User = Depends(auth_manager)):
    # CAMBIO: Llamada directa con await porque ejecutar_agente ahora es async
    result = await orchestrator.ejecutar_agente(
        mensaje_usuario=payload.question,
        user_id=user.email,
        session_id=payload.session_id,
        files=None,
    )
    return {"answer": result["reply_text"], "session_id": result["session_id"]}
# endregion

# -----------------------------------------------------------------------------
# region               ENDPOINT: CARGA DE ARCHIVOS
# -----------------------------------------------------------------------------
@chat_router.post("/upload")
async def chat_upload(
    question: str = Form(...),
    session_id: str | None = Form(default=None),
    files: list[UploadFile] = File(...),
    user: User = Depends(auth_manager),
):
    # --- Validaciones de MimeType (Se mantienen igual) ---
    allowed_mime_types = {
        "application/pdf",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    }
    allowed_extensions = {".pdf", ".doc", ".docx"}

    if not files:
        raise HTTPException(status_code=400, detail="Se requiere al menos un archivo.")

    for f in files:
        filename = f.filename or ""
        ext = os.path.splitext(filename.lower())[1]
        ctype = (f.content_type or "").lower()

        if ext not in allowed_extensions:
            raise HTTPException(
                status_code=415,
                detail=f"Archivo no permitido: {filename}. Solo se aceptan archivos PDF y Word (.doc, .docx).",
            )

        if ctype and ctype not in allowed_mime_types:
            raise HTTPException(
                status_code=415,
                detail=f"Tipo de archivo no permitido: {filename} ({f.content_type}). Solo archivos PDF y Word.",
            )

    session_id = session_id or str(uuid.uuid4())

    # --- CAMBIO PRINCIPAL AQUÍ ---
    # Eliminamos asyncio.to_thread.
    # Pasamos los objetos 'files' (UploadFile) directamente.
    # El orchestrator se encargará de hacer 'await file.read()' internamente.
    
    result = await orchestrator.ejecutar_agente(
        mensaje_usuario=question,
        user_id=user.email,
        session_id=session_id,
        files=files,
    )
    
    return {"answer": result["reply_text"], "session_id": result["session_id"]}

# endregion

# -----------------------------------------------------------------------------
# region               ENDPOINT: DESCARGA DE ARCHIVOS
# -----------------------------------------------------------------------------
@download_router.get("/chat/download")
async def download_doc(
    file: str = Query(...),
    user: User = Depends(auth_manager),
):
    data = downloader.download_bytes(file)
    filename = file.split("/")[-1] or "documento.docx"

    return StreamingResponse(
        io.BytesIO(data),
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
    sessions = cosmos_db.get_user_sessions(user_id)  
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
        session = cosmos_db.sessions_container.read_item(item=conversation_id, partition_key=conversation_id)
    except exceptions.CosmosResourceNotFoundError:
        return ResponseHTTPOneSession(conversation_id=conversation_id, conversation_name="", messages=[])

    if session.get("user_id") != user.email:
        raise HTTPException(status_code=403, detail="No autorizado para ver esta sesión.")

    raw_msgs = cosmos_db.get_session_messages(conversation_id)  # sin await

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
        session = cosmos_db.sessions_container.read_item(item=conversation_id, partition_key=conversation_id)
    except exceptions.CosmosResourceNotFoundError:
        raise HTTPException(status_code=404, detail="Sesión no encontrada.")

    if session.get("user_id") != user.email:
        raise HTTPException(status_code=403, detail="No autorizado para eliminar esta sesión.")

    cosmos_db.delete_session(conversation_id)

    return {
        "message": f"Sesión {conversation_id} eliminada correctamente.",
        "deleted_count": 1
    }

# endregion
