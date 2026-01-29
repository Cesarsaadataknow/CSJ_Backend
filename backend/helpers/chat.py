import io
import uuid
from fastapi import APIRouter, UploadFile, File, Form, Depends, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from core.retrieval import retrieve_from_index
from core.ai_services import AIServices
from core.middleware import AuthManager, User
from helpers.document_loader import extract_text_from_file
from helpers.word_writer import generate_word, upload_to_onelake
from helpers.prompts import build_prompt
from helpers.download_doc import OneLakeDownloader
from app.config import settings

downloader = OneLakeDownloader()
cosmos_db = AIServices.AzureCosmosDB()
auth_manager = AuthManager(settings.auth)

chat_router = APIRouter(tags=["chat"])
download_router = APIRouter(tags=["download"])


class ChatJSONRequest(BaseModel):
    question: str
    session_id: str | None = None


# ------------------------------------------------------------------
# INTENTS
# ------------------------------------------------------------------
def detect_intent(question: str) -> str:
    q = question.lower().strip()

    if q.startswith(("hola", "buenos", "saludos", "hey")):
        return "greeting"

    if any(x in q for x in ["soy ", "me llamo ", "mi nombre es "]):
        return "presentation"

    if any(x in q for x in [
        "qué puedes hacer", "que puedes hacer",
        "ayuda", "como puedes ayudarme"
    ]):
        return "capabilities"

    if q in {"sí", "si", "adelante", "genéralo", "genera el documento"}:
        return "confirm_document"

    return "juridical"


# ------------------------------------------------------------------
# ENDPOINTS
# ------------------------------------------------------------------
@chat_router.post("/json")
async def chat_json(payload: ChatJSONRequest, user: User = Depends(auth_manager)):
    return await _process_chat(payload.question, None, payload.session_id, user.email)


@chat_router.post("/upload")
async def chat_upload(
    question: str = Form(...),
    session_id: str | None = Form(None),
    files: list[UploadFile] = File(...),
    user: User = Depends(auth_manager),
):
    return await _process_chat(question, files, session_id, user.email)


@download_router.get("/chat/download")
async def download_doc(file: str = Query(...), user: User = Depends(auth_manager)):
    data = downloader.download_bytes(file)
    filename = file.split("/")[-1]

    return StreamingResponse(
        io.BytesIO(data),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ------------------------------------------------------------------
# CORE LOGIC
# ------------------------------------------------------------------
async def _process_chat(question, files, session_id, user_id):
    session_id = session_id or str(uuid.uuid4())
    intent = detect_intent(question)

    history = cosmos_db.get_session_messages(session_id)

    # ---------------- PRESENTACIÓN (guardar nombre) ----------------
    if intent == "presentation":
        name = question.split()[-1].capitalize()
        answer = f"Hola {name} 👋\n\n¿En qué te puedo ayudar?"

        cosmos_db.save_answer_rag(
            session_id=session_id,
            user_id=user_id,
            user_question=question,
            ai_response=answer,
            citations=[],
            file_path=None,
            channel="web",
            extra={"user_name": name},
        )

        return {"answer": answer, "session_id": session_id}

    # ---------------- GREETING ----------------
    if intent == "greeting":
        name = None
        for msg in reversed(history):
            if msg.get("extra", {}).get("user_name"):
                name = msg["extra"]["user_name"]
                break

        saludo = f"Hola {name} 👋" if name else "Hola 👋"
        answer = f"{saludo}\n\n¿En qué te puedo ayudar?"

        return {"answer": answer, "session_id": session_id}

    # ---------------- CAPABILITIES ----------------
    if intent == "capabilities":
        answer = (
            "y jurisprudencia de la Corte Suprema de Justicia.\n"
            "Puedo analizar sentencias, explicarte providencias\n"
            "y ayudarte a generar documentos jurídicos.\n\n"
            "¿En qué te puedo ayudar?\n\n"
            "Puedo ayudarte con lo siguiente 👇\n"
            "📚 **Análisis jurídico**\n"
            "- Analizar sentencias y autos\n"
            "- Explicar conflictos de competencia\n"
            "📝 **Documentos**\n"
            "- Elaborar proyectos de providencia\n"
            "- Ajustarlos a un formato definido\n"
            "💬 **Conversación guiada**\n"
            "- Mantener contexto\n"
            "- Preguntarte antes de generar documentos\n\n"
            "¿Qué te gustaría hacer ahora?"
        )

        return {"answer": answer, "session_id": session_id}

    # ---------------- CONFIRMAR DOCUMENTO ----------------
    if intent == "confirm_document":
        pending = None
        for msg in reversed(history):
            if msg.get("extra", {}).get("status") == "awaiting_confirmation":
                pending = msg["extra"]["full_context"]
                break

        if not pending:
            return {
                "answer": "No tengo un contenido previo para generar el documento.",
                "session_id": session_id,
            }

        client = AIServices.chat_client()

        section_map = [
            ("ANTECEDENTES", "antecedentes"),
            ("ACTUACIÓN PROCESAL", "actuacion_procesal"),
            ("ARGUMENTOS DE LAS PARTES", "argumentos_partes"),
            ("CONSIDERACIONES", "consideraciones"),
            ("DECISIÓN", "decision"),
            ("RECOMENDACIONES DE LA IA", "recomendaciones_ia"),
        ]

        sections = {}
        for title, key in section_map:
            completion = client.chat.completions.create(
                model=settings.AZURE_OPENAI_CHAT_DEPLOYMENT,
                messages=[{"role": "user", "content": build_prompt(title, pending)}],
                temperature=0,
            )
            sections[key] = completion.choices[0].message.content

        docx = generate_word("templates/providencia.docx", sections)

        path = upload_to_onelake(
            workspace_name="WS_Resolucion_Conflictos_Competencias_Administrativas",
            lakehouse_name="csj_documentos",
            folder="documentos_generados",
            filename=f"providencia_{session_id}.docx",
            content_bytes=docx,
        )

        return {
            "answer": "📄 Documento generado correctamente.",
            "file": path,
            "session_id": session_id,
        }

    # ---------------- RESPUESTA JURÍDICA ----------------
    docs = retrieve_from_index(question)
    index_context = "\n".join(d.get("texto", "") for d in docs)

    uploaded_text = ""
    if files:
        for f in files:
            uploaded_text += await extract_text_from_file(f)

    full_context = f"{index_context}\n\n{uploaded_text}"

    client = AIServices.chat_client()
    completion = client.chat.completions.create(
        model=settings.AZURE_OPENAI_CHAT_DEPLOYMENT,
        messages=[{"role": "user", "content": full_context}],
        temperature=0,
    )

    answer = completion.choices[0].message.content

    cosmos_db.save_answer_rag(
        session_id=session_id,
        user_id=user_id,
        user_question=question,
        ai_response=answer,
        citations=[],
        file_path=None,
        channel="web",
        extra={"status": "awaiting_confirmation", "full_context": full_context},
    )

    return {
        "answer": answer + "\n\n¿Deseas que genere el documento en Word?",
        "ask_generate_document": True,
        "session_id": session_id,
    }


# import io
# import uuid
# from fastapi import APIRouter, UploadFile, File, Form, Depends, Query, HTTPException
# from fastapi.responses import StreamingResponse
# from pydantic import BaseModel
# from core.retrieval import retrieve_from_index
# from core.ai_services import AIServices
# from core.middleware import AuthManager, User
# from helpers.document_loader import extract_text_from_file
# from helpers.word_writer import generate_word, upload_to_onelake
# from helpers.prompts import build_prompt
# from helpers.download_doc import OneLakeDownloader
# from app.config import settings

# downloader = OneLakeDownloader()
# cosmos_db = AIServices.AzureCosmosDB()
# auth_manager = AuthManager(settings.auth)


# chat_router = APIRouter(tags=["chat"])
# download_router = APIRouter(tags=["download"])


# class ChatJSONRequest(BaseModel):
#     question: str
#     session_id: str | None = None

# @chat_router.post("/")
# async def chat(
#     question: str = Form(...),
#     session_id: str | None = Form(default=None),
#     files: list[UploadFile] | None = File(default=None),
#     user: User = Depends(auth_manager),           
# ):
#     return await _process_chat(
#         question, files, session_id=session_id, user_id=user.email 
#     )

# @chat_router.post("/json")
# async def chat_json(
#     payload: ChatJSONRequest,
#     user: User = Depends(auth_manager),              
# ):
#     return await _process_chat(
#         payload.question, files=None, session_id=payload.session_id, user_id=user.email
#     )

# @chat_router.post("/upload")
# async def chat_upload(
#     question: str = Form(...),
#     session_id: str | None = Form(default=None),
#     files: list[UploadFile] = File(...),
#     user: User = Depends(auth_manager),             
# ):
#     return await _process_chat(
#         question, files, session_id=session_id, user_id=user.email
#     )

# @download_router.get("/chat/download")
# async def download_doc(
#     file: str = Query(...),
#     user: User = Depends(auth_manager),
# ):
#     data = downloader.download_bytes(file)
#     filename = file.split("/")[-1] or "documento.docx"

#     return StreamingResponse(
#         io.BytesIO(data),
#         media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
#         headers={"Content-Disposition": f'attachment; filename="{filename}"'},
#     )


# async def _process_chat(
#     question: str,
#     files: list[UploadFile] | None,
#     session_id: str | None,
#     user_id: str | None,                            
# ):
#     if not session_id:
#         session_id = str(uuid.uuid4())

#     uploaded_text = ""
#     uploaded_files = []

#     if files:
#         for file in files:
#             extracted = extract_text_from_file(file)
#             uploaded_text += f"\n\n[DOCUMENTO: {file.filename}]\n{extracted}"
#             uploaded_files.append(file.filename)

#     retrieved_docs = retrieve_from_index(question)

#     index_context = ""
#     citations = []
#     retrieved_ids = []

#     for i, d in enumerate(retrieved_docs, 1):
#         texto = d.get("texto", "").strip()
#         if not texto:
#             continue
#         index_context += f"[ÍNDICE {i}]\n{texto}\n\n"
#         citations.append(f"[ÍNDICE {i}] ID: {d.get('id')}")
#         retrieved_ids.append(d.get("id"))

#     if not index_context.strip() and not uploaded_text.strip():
#         answer = "No se encontró información suficiente en el índice ni en los documentos cargados."

#         cosmos_db.save_answer_rag(
#             session_id=session_id,
#             user_id=user_id,  
#             user_question=question,
#             ai_response=no_info_response["answer"],
#             citations=[],
#             file_path=None,
#             channel="web",
#             extra={"status": "no_context"}
#         )

#         return {
#             "answer": answer,
#             "citations": [],
#             "session_id": session_id
#         }

#     full_context = f"""
# DOCUMENTOS DEL ÍNDICE (JURISPRUDENCIA):
# {index_context}

# DOCUMENTOS CARGADOS POR EL USUARIO:
# {uploaded_text}
# """

#     system_prompt = (
#         "Eres un asistente jurídico experto en resolución de conflictos de competencias. "
#         "Responde exclusivamente con base en los documentos proporcionados. "
#         "Utiliza lenguaje jurídico formal y preciso."
#     )

#     client = AIServices.chat_client()

#     sections = {}
#     section_map = [
#         ("I. ANTECEDENTES", "antecedentes"),
#         ("II. CONSIDERACIONES", "consideraciones"),
#         ("III. PROBLEMA JURÍDICO", "problema"),
#         ("IV. DECISIÓN", "decision"),
#     ]

#     for title, key in section_map:
#         completion = client.chat.completions.create(
#             model=settings.AZURE_OPENAI_CHAT_DEPLOYMENT,
#             messages=[
#                 {"role": "system", "content": system_prompt},
#                 {"role": "user", "content": build_prompt(title, full_context)},
#             ],
#             temperature=0,
#         )
#         sections[key] = completion.choices[0].message.content

#     docx_bytes = generate_word(
#         template_path="templates/providencia.docx",
#         content=sections
#     )

#     folder = "documentos_generados/"
#     filename = f"providencia_{session_id}.docx"

#     WORKSPACE_NAME = "WS_Resolucion_Conflictos_Competencias_Administrativas"
#     LAKEHOUSE_NAME = "csj_documentos"

#     onelake_path = upload_to_onelake(
#     workspace_name=WORKSPACE_NAME,
#     lakehouse_name=LAKEHOUSE_NAME,
#     folder=folder,
#     filename=filename,
#     content_bytes=docx_bytes
# )

#     onelake_dfs_url = onelake_path
#     if not onelake_dfs_url.startswith("http"):
#         rel = onelake_dfs_url.lstrip("/")
#         if not rel.lower().startswith("files/"):
#             rel = f"Files/{rel}"
#         onelake_dfs_url = (
#             f"https://onelake.dfs.fabric.microsoft.com/"
#             f"{WORKSPACE_NAME}/{LAKEHOUSE_NAME}.Lakehouse/{rel}"
#         )

#     cosmos_db.save_answer_rag(
#         session_id=session_id,
#         user_id=user_id,
#         user_question=question,
#         ai_response=sections,
#         citations=citations,
#         file_path=onelake_dfs_url,  
#         channel="web",
#         extra={
#             "uploaded_files": uploaded_files,
#             "retrieved_ids": retrieved_ids,
#             "status": "ok",
#         }
#     )

#     return {
#         "answer": sections,
#         "citations": citations,
#         "file": onelake_dfs_url,  
#         "session_id": session_id,
#     }
