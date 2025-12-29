from fastapi import APIRouter, UploadFile, File, Form
from core.retrieval import retrieve_from_index
from core.ai_services import AIServices
from helpers.document_loader import extract_text_from_file
from app.config import settings

chat_router = APIRouter(tags=["chat"])

TEXTOPROVIDENCIA = """
(TEXTO BASE DE PROVIDENCIA AQUÍ)
"""

@chat_router.post("/")
async def chat(
    question: str = Form(...),
    files: list[UploadFile] | None = File(default=None)
):
    # 1️⃣ Texto de documentos cargados
    uploaded_text = ""

    if files:
        for file in files:
            extracted = await extract_text_from_file(file)
            uploaded_text += f"\n\n[DOCUMENTO: {file.filename}]\n{extracted}"

    # 2️⃣ Recuperar desde índice (Fabric / AI Search)
    retrieved_docs = retrieve_from_index(question)

    index_context = ""
    citations = []

    for i, d in enumerate(retrieved_docs, 1):
        if d["texto"].strip():
            index_context += f"[ÍNDICE {i}]\n{d['texto']}\n\n"
            citations.append(f"[ÍNDICE {i}] ID: {d['id']}")

    # 3️⃣ Prompt final (RAG + Documento + Providencia)
    system_prompt = """
Eres un asistente jurídico experto en resolución de conflictos de competencias.
Responde SOLO con base en los documentos proporcionados.
"""

    user_prompt = f"""
TEXTO PROVIDENCIA BASE:
{TEXTOPROVIDENCIA}

DOCUMENTOS CARGADOS:
{uploaded_text}

DOCUMENTOS DEL ÍNDICE:
{index_context}

PREGUNTA:
{question}
"""

    client = AIServices.chat_client()

    completion = client.chat.completions.create(
        model=settings.AZURE_OPENAI_CHAT_DEPLOYMENT,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0,
    )

    return {
        "answer": completion.choices[0].message.content,
        "citations": citations,
    }



# from fastapi import APIRouter, UploadFile, File, Form
# from core.retrieval import retrieve_from_index
# from core.ai_services import AIServices
# from app.config import settings

# chat_router = APIRouter(tags=["chat"])

# @chat_router.post("/")
# async def chat(
#     question: str = Form(...),
#     files: list[UploadFile] | None = File(default=None)
# ):
#     # 1️⃣ Recuperar contexto desde Azure AI Search (Fabric)
#     retrieved_docs = retrieve_from_index(question)

#     index_context = ""
#     citations = []

#     for i, d in enumerate(retrieved_docs, 1):
#         if not d["texto"].strip():
#             continue

#         index_context += f"[ÍNDICE {i}]\n{d['texto']}\n\n"
#         citations.append(f"[ÍNDICE {i}] ID: {d['id']}")

#     if not index_context.strip():
#         return {
#             "answer": "La información no se encuentra en los documentos disponibles.",
#             "citations": []
#         }

#     system_prompt = """
# Eres un asistente jurídico especializado en providencias de resolución de conflictos.
# Responde SOLO con base en los documentos proporcionados.
# """

#     user_prompt = f"""
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
