
from typing import List, Optional, Literal
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Depends, Query, Path
import pdfkit
import tempfile
from helpers.schema_http import (
    RequestHTTPChat, ResponseHTTPChat,
    RequestHTTPVote, ResponseHTTPVote,
    ResponseHTTPSessions, ResponseHTTPOneSession,
    ResponseHTTPDelete
)
from bs4 import BeautifulSoup
from helpers.utils import genereta_id
from inference.graph import PDFChatAgent
from helpers.utils import extract_text_content,extract_word_content,extract_excel_content, extract_pptx_content

from core.ai_services import AIServices
from core.config import settings
from core.middleware import AuthManager, User

auth_manager = AuthManager(settings.auth)
chat_router = APIRouter()

# Instancias de servicios
pdf_extractor = AIServices.PdfProcessor()
cosmos_db = AIServices.CosmosDBClient()
openai_client = AIServices.AzureOpenAI()
pdf_chat_agent = PDFChatAgent()

@chat_router.post(
    "/message",
    response_model=ResponseHTTPChat
)
async def endpoint_message(request: RequestHTTPChat, user: User = Depends(auth_manager)):
    """
    Endpoint para procesar el mensaje y generar respuesta.
    """
    if pdf_chat_agent is None:
        raise HTTPException(status_code=500, detail="chat_agent no está inicializado")

    try:
        new_state, doc = await pdf_chat_agent.invoke_flow(
            user_input=request.query,
            pdf_text=None,
            message_id = request.message_id,
            conversation_id=request.conversation_id,
            conversation_name=request.conversation_name,
            user_id=user.email,
            extra_params= {
                "flag_modifier": request.flag_modifier,
                "model_name": request.model_name,
                "search_tool": request.search_tool
                }
        )
        final_msg = new_state["messages"][-1]
        return {"id": doc.get("id"), "text": final_msg.content}
    except Exception:
        return {"id": genereta_id(), "text": "Error al procesar el mensaje, intente nuevamente."}
    

@chat_router.post("/vote", response_model=ResponseHTTPVote)
async def endpoint_vote(request: RequestHTTPVote, _: User = Depends(auth_manager)):
    """
    Ejemplo de cómo se maneja el voto o rating de un documento en Cosmos.
    """
    try:
        res = await cosmos_db.update_document_rate(document_id=request.id,  rate=request.rate, partition_key=request.thread_id, )
    except Exception as e:
        res = f"Error al actualizar el voto: {str(e)}"
    return {"id": genereta_id(), "text": "OK", "state": res}

@chat_router.post("/attachment", response_model=dict)
async def upload_attachment(
    message_id: str = Form(...),
    conversation_id: str = Form(...),
    conversation_name: str = Form(...),
    message: str = Form(...),
    files: List[UploadFile] = File(...),
    flag_modifier: Optional[bool] = Form(...),
    model_name: Optional[Literal["gpt-4o", "o1", "o1-mini"]] = Form(...),
    search_tool: Optional[bool] = Form(...),
    user: User = Depends(auth_manager)
):
    """
    Endpoint para cargar uno o varios archivos (PDF, TXT, DOC/DOCX, XLS/XLSX)
    y extraer su contenido.
    """
    if message is None or message.strip() == "":
        message = "Describa el contenido de los archivos adjuntos proporcionados."
    if not files:
        raise HTTPException(status_code=400, detail="Se requiere al menos un archivo.")

    # Lista de content types permitidos
    allowed_types = [
        "application/pdf",
        "text/plain",
        "text/html",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "image/jpeg",
        "image/jpg",
        "image/png",
        "image/bmp",
        "image/tif",
        "image/tiff",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "application/vnd.ms-powerpoint"
    ]

    files_contents = []
    for file in files:
        if file.content_type not in allowed_types:
            raise HTTPException(
                status_code=400, 
                detail=f"Tipo de archivo no soportado: {file.content_type}. "
                       "Solo se permiten PDF, TXT, DOC/DOCX, XLS/XLSX, HTML, JPG, PNG, BMP, TIFF y PPTX."
            )
        content = await file.read()

        if file.content_type == "application/pdf":
            text = content
            doc_type = "pdf"
        elif file.content_type == "text/plain":
            text = extract_text_content(content)
            doc_type = "txt"
        elif file.content_type in [
            "application/msword",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ]:
            text = extract_word_content(content)
            doc_type = "word"
            
        elif file.content_type in [
            "application/vnd.ms-excel",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ]:
            text = extract_excel_content(content)
            doc_type = "excel"

        elif file.content_type in ["image/jpeg", "image/jpg",  "image/png", "image/bmp", "image/tiff","image/tif"]:
            text = openai_client.analyze_image(image=content, msg=message, mime_type=file.content_type)
            doc_type = "image"

        elif file.content_type in [
            "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            "application/vnd.ms-powerpoint"
        ]:
            text = extract_pptx_content(content)
            doc_type = "pptx"
        elif file.content_type == "text/html":
            if not content.strip():
                raise HTTPException(status_code=400, detail="Archivo HTML vacío o inválido")
            
            soup = BeautifulSoup(content, "html.parser")
            for tag in soup.find_all(["script", "link", "img", "iframe"]):
                tag.decompose()
            html_limpio = str(soup)


            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as temp_pdf:
                options = {
                    'enable-local-file-access': '',
                    'quiet': '',
                    'disable-javascript': '',
                    'no-images': '',
                }

                try:
                    pdfkit.from_string(html_limpio, temp_pdf.name, options=options)
                except OSError as e:
                    raise HTTPException(status_code=500, detail=f"Error al convertir HTML a PDF: {e}")
                
                with open(temp_pdf.name, "rb") as f:
                    content = f.read()

            doc_type = "pdf"
            text = content
        else:
            text = ""
        
        files_contents.append({
            "file_name": file.filename,
            "content": text,
            "doc_type":doc_type
        })

    # Aquí se llama a la función que procesa el contenido extraído.
    # Si bien en el ejemplo original se usaba 'pdf_extractor.main', quizá debas refactorizarla
    # para que trabaje con distintos tipos de archivos. Por ahora se mantiene el nombre.
    text_content, response_info = await pdf_extractor.main(
        user_id=user.email,
        conversation_id=conversation_id,
        files_obj=files_contents
    )

    if not text_content:
        raise HTTPException(status_code=400, detail="No se pudo extraer contenido de los archivos.")

    if response_info.get('read_files'):
        read_files = [res.get('file_name') for res in response_info.get('read_files')]
    else:
        read_files = None
    new_state, doc = await pdf_chat_agent.invoke_flow(
        user_input=message,
        pdf_text=read_files,
        message_id=message_id,
        conversation_id=conversation_id,
        conversation_name=conversation_name,
        user_id=user.email,
        extra_params = {
                    "flag_modifier": flag_modifier,
                    "model_name":model_name,
                    "search_tool":search_tool
                }   
        )

    return {
        "id": doc.get('id'),
        "text": new_state['messages'][-1].content,
    }

@chat_router.get("/sessions", response_model=ResponseHTTPSessions)
async def read_sessions(user: User = Depends(auth_manager)):
    """
    Ruta para cargar las sesiones (conversaciones) de un usuario.
    Lanza HTTP 404 si no existen conversaciones para ese usuario.
    """
    user_id = user.email
    response = await cosmos_db.get_user_conversations(user_id)
    
    if not response:
        print(f"No se encontraron conversaciones para el user_id {user_id}.")
        response = []
    return {"sessions": response}

@chat_router.get("/get_one_session", response_model=ResponseHTTPOneSession)
async def read_one_session(conversation_id: str = Query(...), _: User = Depends(auth_manager)):
    """
    Ruta para cargar los documentos (mensajes) de una sola conversación.
    Lanza HTTP 404 si no existe o no se encontraron documentos en esa conversación.
    """
    response = await cosmos_db.get_documents_by_thread_id(conversation_id)

    if not response:
        response = ResponseHTTPOneSession(
            conversation_id=conversation_id,
            conversation_name="",
            messages=[]
        )
    return response

@chat_router.delete("/delete_one_session/{conversation_id}", response_model=ResponseHTTPDelete)
async def delete_one_session(conversation_id: str = Path(...), _: User = Depends(auth_manager)):
    """
    Ruta para eliminar todos los documentos (mensajes) de una sola conversación.
    Lanza HTTP 404 si no se encontró ninguna conversación con ese ID.
    """
    deleted_count = await cosmos_db.delete_documents_by_conversation_id(conversation_id)

    if deleted_count == 0:
        raise HTTPException(
            status_code=404,
            detail=f"No se encontraron documentos para eliminar con el conversation_id {conversation_id}."
        )

    return {
        "message": f"Se eliminaron {deleted_count} documentos para conversation_id {conversation_id}.",
        "deleted_count": deleted_count,
    }