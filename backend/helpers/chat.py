# -----------------------------------------------------------------------------
# region                           IMPORTS
# -----------------------------------------------------------------------------
import io
import uuid
from fastapi import APIRouter, UploadFile, File, Form, Depends, Query, HTTPException, Path
from fastapi.responses import StreamingResponse
from datetime import datetime
from core.retrieval import retrieve_from_index
from azure.cosmos import exceptions
from core.ai_services import AIServices
from core.middleware import AuthManager, User
from helpers.document_loader import extract_text_from_file
from helpers.word_writer import generate_word, upload_to_onelake
from helpers.prompts import build_prompt
from helpers.download_doc import OneLakeDownloader
from app.config import settings
from helpers.schema_http import (
    ChatJSONRequest, ResponseHTTPSessions, 
    ResponseHTTPOneSession,ResponseHTTPDelete, Message
)
# endregion

# -----------------------------------------------------------------------------
# region               INICIALIZACIÓN Y CONFIGURACIÓN
# -----------------------------------------------------------------------------
downloader = OneLakeDownloader()
cosmos_db = AIServices.AzureCosmosDB()
auth_manager = AuthManager(settings.auth)
chat_router = APIRouter(tags=["chat"])
download_router = APIRouter(tags=["download"])
# endregion


# -----------------------------------------------------------------------------
# region               ENDPOINT: PROCESAR MENSAJE DE CHAT
# -----------------------------------------------------------------------------
@chat_router.post("/json")
async def chat_json(
    payload: ChatJSONRequest,
    user: User = Depends(auth_manager),
):
    return await _process_chat(
        payload.question,
        files=None,
        session_id=payload.session_id,
        user_id=user.email
    )
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
    return await _process_chat(
        question,
        files=files,
        session_id=session_id,
        user_id=user.email
    )
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

# -----------------------------------------------------------------------------
# region                 FUNCION DE PROCESAMIENTO Y GUARDADO
# -----------------------------------------------------------------------------

MAX_CONVERSATIONS_PER_USER = 10
MAX_FILES_PER_SESSION = 40

async def _process_chat(
    question: str,
    files: list[UploadFile] | None,
    session_id: str | None,
    user_id: str | None,
):
    # ----------------------------
    # Validación usuario
    # ----------------------------
    if not user_id:
        raise HTTPException(status_code=401, detail="Usuario no autenticado.")

    # ----------------------------
    # Límite 10 conversaciones
    # ----------------------------
    if not session_id:
        user_sessions = cosmos_db.get_user_sessions(user_id)  
        if len(user_sessions) >= MAX_CONVERSATIONS_PER_USER:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"Límite alcanzado: máximo {MAX_CONVERSATIONS_PER_USER} conversaciones por usuario. "
                    f"Por favor elimina una conversacion del panel izquierdo para crear una nueva."
                )
            )
        session_id = str(uuid.uuid4())

    # ----------------------------
    # Límite 40 documentos por sesión
    # ----------------------------
    uploaded_files = []
    uploaded_text = ""

    if files:
        # contar lo ya subido en Cosmos
        existing_files = cosmos_db.count_uploaded_files(session_id)
        if existing_files + len(files) > MAX_FILES_PER_SESSION:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"Límite alcanzado: máximo {MAX_FILES_PER_SESSION} documentos por sesión. "
                    f"Ya hay {existing_files} y estás intentando subir {len(files)}."
                )
            )

        for file in files:
            extracted = extract_text_from_file(file)
            uploaded_text += f"\n\n[DOCUMENTO: {file.filename}]\n{extracted}"
            uploaded_files.append(file.filename)

    retrieved_docs = retrieve_from_index(question)

    index_context = ""
    citations = []
    retrieved_ids = []

    for i, d in enumerate(retrieved_docs, 1):
        texto = d.get("texto", "").strip()
        if not texto:
            continue
        index_context += f"[ÍNDICE {i}]\n{texto}\n\n"
        citations.append(f"[ÍNDICE {i}] ID: {d.get('id')}")
        retrieved_ids.append(d.get("id"))

    if not index_context.strip() and not uploaded_text.strip():
        answer = "No se encontró información suficiente en el índice ni en los documentos cargados."

        cosmos_db.save_answer_rag(
            session_id=session_id,
            user_id=user_id,
            user_question=question,
            ai_response=no_info_response["answer"],
            citations=[],
            file_path=None,
            channel="web",
            extra={"status": "no_context", "uploaded_files": uploaded_files}
        )

        return {
            "answer": answer,
            "citations": [],
            "session_id": session_id
        }

    full_context = f"""
DOCUMENTOS DEL ÍNDICE (JURISPRUDENCIA):
{index_context}

DOCUMENTOS CARGADOS POR EL USUARIO:
{uploaded_text}
"""

    system_prompt = (
        "Eres un asistente jurídico experto en resolución de conflictos de competencias. "
        "Responde exclusivamente con base en los documentos proporcionados. "
        "Utiliza lenguaje jurídico formal y preciso."
    )

    client = AIServices.chat_client()

    sections = {}
    section_map = [
        ("I. ANTECEDENTES", "antecedentes"),
        ("II. CONSIDERACIONES", "consideraciones"),
        ("III. PROBLEMA JURÍDICO", "problema"),
        ("IV. DECISIÓN", "decision"),
    ]

    for title, key in section_map:
        completion = client.chat.completions.create(
            model=settings.AZURE_OPENAI_CHAT_DEPLOYMENT,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": build_prompt(title, full_context)},
            ],
            temperature=0,
        )
        sections[key] = completion.choices[0].message.content

    docx_bytes = generate_word(
        template_path="templates/providencia.docx",
        content=sections
    )

    folder = "documentos_generados/"
    filename = f"providencia_{session_id}.docx"

    WORKSPACE_NAME = "WS_Resolucion_Conflictos_Competencias_Administrativas"
    LAKEHOUSE_NAME = "csj_documentos"

    onelake_path = upload_to_onelake(
        workspace_name=WORKSPACE_NAME,
        lakehouse_name=LAKEHOUSE_NAME,
        folder=folder,
        filename=filename,
        content_bytes=docx_bytes
    )

    onelake_dfs_url = onelake_path
    if not onelake_dfs_url.startswith("http"):
        rel = onelake_dfs_url.lstrip("/")
        if not rel.lower().startswith("files/"):
            rel = f"Files/{rel}"
        onelake_dfs_url = (
            f"https://onelake.dfs.fabric.microsoft.com/"
            f"{WORKSPACE_NAME}/{LAKEHOUSE_NAME}.Lakehouse/{rel}"
        )

    cosmos_db.save_answer_rag(
        session_id=session_id,
        user_id=user_id,
        user_question=question,
        ai_response=sections,
        citations=citations,
        file_path=onelake_dfs_url,
        channel="web",
        extra={
            "uploaded_files": uploaded_files,
            "retrieved_ids": retrieved_ids,
            "status": "ok",
        }
    )

    return {
        "answer": sections,
        "citations": citations,
        "file": onelake_dfs_url,
        "session_id": session_id,
    }

# endregion
