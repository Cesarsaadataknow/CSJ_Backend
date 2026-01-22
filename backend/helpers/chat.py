
#==================================================================================

import uuid
from fastapi import APIRouter, UploadFile, File, Form
from pydantic import BaseModel
from datetime import datetime
from core.retrieval import retrieve_from_index
from core.ai_services import AIServices 
from helpers.document_loader import extract_text_from_file
from helpers.word_writer import generate_word, upload_to_onelake
from helpers.prompts import build_prompt
from app.config import settings



# -----------------------------------------------------------------------------
# region               INICIALIZACIÓN Y CONFIGURACIÓN
# -----------------------------------------------------------------------------
# Instancias de servicios
cosmos_db = AIServices.AzureCosmosDB()
chat_router = APIRouter(tags=["chat"])
# endregion


# =====================================================
# MODELO PARA SWAGGER / JSON
# =====================================================
class ChatJSONRequest(BaseModel):
    question: str
    session_id: str | None = None
    user_id: str | None = None   # opcional si lo tienes


# =====================================================
# ENDPOINT PRINCIPAL (multipart/form-data)
# =====================================================
@chat_router.post("/")
async def chat(
    question: str = Form(...),
    session_id: str | None = Form(default=None),   
    user_id: str | None = Form(default=None),    
    files: list[UploadFile] | None = File(default=None)
):
    return await _process_chat(question, files, session_id=session_id, user_id=user_id)


# =====================================================
# ENDPOINT PARA SWAGGER (application/json)
# =====================================================
@chat_router.post("/json")
async def chat_json(payload: ChatJSONRequest):
    return await _process_chat(payload.question, files=None, session_id=payload.session_id, user_id=payload.user_id)


# =====================================================
# ENDPOINT PARA SWAGGER (upload)
# =====================================================
@chat_router.post("/upload")
async def chat_upload(
    question: str = Form(...),
    session_id: str | None = Form(default=None),  
    user_id: str | None = Form(default=None),     
    files: list[UploadFile] = File(...)
):
    return await _process_chat(question, files, session_id=session_id, user_id=user_id)


# =====================================================
# LÓGICA CENTRAL (REUTILIZABLE)
# =====================================================
async def _process_chat(
    question: str,
    files: list[UploadFile] | None,
    session_id: str | None,
    user_id: str | None
):
    # 0) Asegurar session_id
    if not session_id:
        session_id = str(uuid.uuid4())

    # -------------------------------------------------
    # 1️⃣ Texto de documentos cargados
    # -------------------------------------------------
    uploaded_text = ""
    uploaded_files = []

    if files:
        for file in files:
            extracted = extract_text_from_file(file)  # SIN await
            uploaded_text += f"\n\n[DOCUMENTO: {file.filename}]\n{extracted}"
            uploaded_files.append(file.filename)

    # -------------------------------------------------
    # 2️⃣ Recuperar desde índice
    # -------------------------------------------------
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

    # Caso sin contexto: también lo guardamos en Cosmos
    if not index_context.strip() and not uploaded_text.strip():
        no_info_response = {
            "answer": "No se encontró información suficiente en el índice ni en los documentos cargados.",
            "citations": [],
            "session_id": session_id,
        }

        cosmos_db.save_answer_rag(
            session_id=session_id,
            user_id=user_id,
            user_question=question,
            ai_response=no_info_response["answer"],  # string
            citations=[],
            file_path=None,
            channel="web",
            extra={
                "uploaded_files": uploaded_files,
                "retrieved_ids": retrieved_ids,
                "status": "no_context"
            }
        )

        return no_info_response

    # -------------------------------------------------
    # 3️⃣ Contexto unificado (RAG)
    # -------------------------------------------------
    full_context = f"""
DOCUMENTOS DEL ÍNDICE (JURISPRUDENCIA):
{index_context}

DOCUMENTOS CARGADOS POR EL USUARIO:
{uploaded_text}
"""

    # -------------------------------------------------
    # 4️⃣ Azure OpenAI
    # -------------------------------------------------
    system_prompt = (
        "Eres un asistente jurídico experto en resolución de conflictos de competencias. "
        "Responde exclusivamente con base en los documentos proporcionados. "
        "Utiliza lenguaje jurídico formal y preciso."
    )

    client = AIServices.chat_client()

    # -------------------------------------------------
    # 5️⃣ Generar secciones jurídicas
    # -------------------------------------------------
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

    # -------------------------------------------------
    # 6️⃣ Generar Word
    # -------------------------------------------------
    docx_bytes = generate_word(
        template_path="templates/providencia.docx",
        content=sections
    )

    # destino en OneLake
    folder = f"documentos_generados/"
    filename = f"providencia_{session_id}.docx"

    WORKSPACE_NAME = "WS_Resolucion_Conflictos_Competencias_Administrativas"      # <-- pon el nombre real del workspace de Fabric
    LAKEHOUSE_NAME = "csj_documentos"    # <-- por tu screenshot

    onelake_path = upload_to_onelake(
        workspace_name=WORKSPACE_NAME,
        lakehouse_name=LAKEHOUSE_NAME,
        folder=folder,
        filename=filename,
        content_bytes=docx_bytes
    )

    # -------------------------------------------------
    # 7️⃣ Guardar en Cosmos (session + message)
    # -------------------------------------------------
    cosmos_db.save_answer_rag(
        session_id=session_id,
        user_id=user_id,
        user_question=question,
        ai_response=sections,         
        citations=citations,
        file_path=onelake_path,
        channel="web",
        extra={
            "uploaded_files": uploaded_files,
            "retrieved_ids": retrieved_ids,
            "status": "ok"
        }
    )

    # -------------------------------------------------
    # 8️⃣ Respuesta final
    # -------------------------------------------------
    return {
        "answer": sections,
        "citations": citations,
        "file": onelake_path,
        "session_id": session_id,  # 👈 SUPER IMPORTANTE
    }


# #===========================================================================================
# from fastapi import APIRouter, UploadFile, File, Form
# from core.retrieval import retrieve_from_index
# from core.ai_services import AIServices
# from helpers.document_loader import extract_text_from_file
# from helpers.word_writer import generate_word
# from helpers.prompts import build_prompt
# from app.config import settings

# chat_router = APIRouter(tags=["chat"])


# @chat_router.post("/")
# async def chat(
#     question: str = Form(...),
#     files: list[UploadFile] | None = File(default=None)
# ):
#     # -------------------------------------------------
#     # 1️⃣ Texto de documentos cargados (PDF / Word)
#     # -------------------------------------------------
#     uploaded_text = ""

#     if files:
#         for file in files:
#             extracted = extract_text_from_file(file)  # SIN await
#             uploaded_text += f"\n\n[DOCUMENTO: {file.filename}]\n{extracted}"

#     # -------------------------------------------------
#     # 2️⃣ Recuperar desde índice (Fabric / AI Search)
#     # -------------------------------------------------
#     retrieved_docs = retrieve_from_index(question)

#     index_context = ""
#     citations = []

#     for i, d in enumerate(retrieved_docs, 1):
#         texto = d.get("texto", "").strip()
#         if not texto:
#             continue

#         index_context += f"[ÍNDICE {i}]\n{texto}\n\n"
#         citations.append(f"[ÍNDICE {i}] ID: {d.get('id')}")

#     if not index_context.strip() and not uploaded_text.strip():
#         return {
#             "answer": "No se encontró información suficiente en el índice ni en los documentos cargados.",
#             "citations": []
#         }

#     # -------------------------------------------------
#     # 3️⃣ Contexto unificado (RAG)
#     # -------------------------------------------------
#     full_context = f"""
# DOCUMENTOS DEL ÍNDICE (JURISPRUDENCIA):
# {index_context}

# DOCUMENTOS CARGADOS POR EL USUARIO:
# {uploaded_text}
# """

#     # -------------------------------------------------
#     # 4️⃣ Azure OpenAI
#     # -------------------------------------------------
#     system_prompt = (
#         "Eres un asistente jurídico experto en resolución de conflictos de competencias. "
#         "Responde exclusivamente con base en los documentos proporcionados. "
#         "Utiliza lenguaje jurídico formal y preciso."
#     )

#     client = AIServices.chat_client()

#     # -------------------------------------------------
#     # 5️⃣ Generar secciones jurídicas
#     # -------------------------------------------------
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

#     # -------------------------------------------------
#     # 6️⃣ Generar Word desde plantilla
#     # -------------------------------------------------
#     output_path = "output/providencia_generada.docx"

#     generate_word(
#         template_path="templates/providencia.docx",
#         output_path=output_path,
#         content=sections
#     )

#     # -------------------------------------------------
#     # 7️⃣ Respuesta final
#     # -------------------------------------------------
#     return {
#         "answer": sections,
#         "citations": citations,
#         "file": output_path
#     }

#=======================================================================================================00

# from fastapi import APIRouter, UploadFile, File, Form
# from core.retrieval import retrieve_from_index
# from core.ai_services import AIServices
# from helpers.document_loader import extract_text_from_file
# from app.config import settings

# chat_router = APIRouter(tags=["chat"])

# @chat_router.post("/")
# async def chat(
#     question: str = Form(...),
#     files: list[UploadFile] | None = File(default=None)
# ):
#     # -------------------------------------------------
#     # 1️⃣ Texto de documentos cargados (PDF / Word)
#     # -------------------------------------------------
#     uploaded_text = ""

#     if files:
#         for file in files:
#             # extract_text_from_file ES SINCRONA → NO await
#             extracted = extract_text_from_file(file)
#             uploaded_text += f"\n\n[DOCUMENTO: {file.filename}]\n{extracted}"

#     # -------------------------------------------------
#     # 2️⃣ Recuperar desde índice (Fabric / AI Search)
#     # -------------------------------------------------
#     retrieved_docs = retrieve_from_index(question)

#     index_context = ""
#     citations = []

#     for i, d in enumerate(retrieved_docs, 1):
#         texto = d.get("texto", "").strip()
#         if not texto:
#             continue

#         index_context += f"[ÍNDICE {i}]\n{texto}\n\n"
#         citations.append(f"[ÍNDICE {i}] ID: {d.get('id')}")

#     if not index_context.strip() and not uploaded_text.strip():
#         return {
#             "answer": "No se encontró información suficiente en el índice ni en los documentos cargados.",
#             "citations": []
#         }

#     # -------------------------------------------------
#     # 3️⃣ Prompt (RAG + Documentos)
#     # -------------------------------------------------
#     system_prompt = (
#         "Eres un asistente jurídico experto en resolución de conflictos de competencias. "
#         "Responde exclusivamente con base en los documentos proporcionados. "
#         "Utiliza lenguaje jurídico formal y preciso."
#     )

#     user_prompt = f"""
# DOCUMENTOS DEL ÍNDICE (JURISPRUDENCIA):
# {index_context}

# DOCUMENTOS CARGADOS POR EL USUARIO:
# {uploaded_text}

# PREGUNTA:
# {question}
# """

#     # -------------------------------------------------
#     # 4️⃣ Llamada a Azure OpenAI
#     # -------------------------------------------------
#     client = AIServices.chat_client()

#     completion = client.chat.completions.create(
#         model=settings.AZURE_OPENAI_CHAT_DEPLOYMENT,
#         messages=[
#             {"role": "system", "content": system_prompt},
#             {"role": "user", "content": user_prompt},
#         ],
#         temperature=0,
#     )

#     answer = completion.choices[0].message.content

#     return {
#         "answer": answer,
#         "citations": citations,
#     }

#-------------------------------------------------------------------------------------------------------------

# from fastapi import APIRouter, UploadFile, File, Form
# from core.retrieval import retrieve_from_index
# from core.ai_services import AIServices
# from helpers.document_loader import extract_text_from_file
# from app.config import settings


# chat_router = APIRouter(tags=["chat"])

# TEXTOPROVIDENCIA = """
# (TEXTO BASE DE PROVIDENCIA AQUÍ)
# """

# @chat_router.post("/")
# async def chat(
#     question: str = Form(...),
#     files: list[UploadFile] | None = File(default=None)
# ):
#     # 1️⃣ Texto de documentos cargados
#     uploaded_text = ""

#     if files:
#         for file in files:
#             extracted = await extract_text_from_file(file)
#             uploaded_text += f"\n\n[DOCUMENTO: {file.filename}]\n{extracted}"

#     # 2️⃣ Recuperar desde índice (Fabric / AI Search)
#     retrieved_docs = retrieve_from_index(question)

#     index_context = ""
#     citations = []

#     for i, d in enumerate(retrieved_docs, 1):
#         if d["texto"].strip():
#             index_context += f"[ÍNDICE {i}]\n{d['texto']}\n\n"
#             citations.append(f"[ÍNDICE {i}] ID: {d['id']}")

#     # 3️⃣ Prompt final (RAG + Documento + Providencia)
#     system_prompt = """
# Eres un asistente jurídico experto en resolución de conflictos de competencias.
# Responde SOLO con base en los documentos proporcionados.
# """

#     user_prompt = f"""
# TEXTO PROVIDENCIA BASE:
# {TEXTOPROVIDENCIA}

# DOCUMENTOS CARGADOS:
# {uploaded_text}

# DOCUMENTOS DEL ÍNDICE:
# {index_context}

# PREGUNTA:
# {question}
# """

#     client = AIServices.chat_client()

#     completion = client.chat.completions.create(
#         model=settings.AZURE_OPENAI_CHAT_DEPLOYMENT,
#         messages=[
#             {"role": "system", "content": system_prompt},
#             {"role": "user", "content": user_prompt},
#         ],
#         temperature=0,
#     )

#     return {
#         "answer": completion.choices[0].message.content,
#         "citations": citations,
#     }
