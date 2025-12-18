from fastapi import APIRouter, UploadFile, File
from pydantic import BaseModel
from core.retrieval import retrieve_from_index
from core.ai_services import AIServices
from helpers.document_loader import load_pdf, load_docx, simple_chunk

chat_router = APIRouter()

class ChatRequest(BaseModel):
    question: str

@chat_router.post("/")
async def chat(
    request: ChatRequest,
    files: list[UploadFile] | None = File(default=None)
):

    # ----------------------------
    # 1. Recuperar desde el índice
    # ----------------------------
    retrieved_docs = await retrieve_from_index(request.question)

    index_context = ""
    citations = []

    for i, d in enumerate(retrieved_docs, 1):
        index_context += f"[ÍNDICE {i}]\n{d['texto']}\n\n"
        citations.append(f"[ÍNDICE {i}] ID: {d['id']}")

    # ----------------------------------
    # 2. Procesar documentos del usuario
    # ----------------------------------
    user_context = ""
    if files:
        for f in files:
            content = await f.read()
            if f.filename.lower().endswith(".pdf"):
                text = load_pdf(content)
            elif f.filename.lower().endswith(".docx"):
                text = load_docx(content)
            else:
                continue

            chunks = simple_chunk(text)
            for c in chunks[:5]:
                user_context += f"[DOCUMENTO USUARIO]\n{c}\n\n"
                citations.append(f"[DOCUMENTO USUARIO] {f.filename}")

    # ----------------------------
    # 3. Prompt legal estricto
    # ----------------------------
    system_prompt = """
Eres un asistente jurídico especializado en providencias de resolución de conflictos.

REGLAS OBLIGATORIAS:
1. Responde ÚNICAMENTE con la información contenida en los documentos proporcionados.
2. NO uses conocimiento externo.
3. NO infieras ni completes información.
4. Si la respuesta no está en los documentos, responde:
   "La información no se encuentra en los documentos disponibles."
5. Toda afirmación debe estar citada.
"""

    user_prompt = f"""
DOCUMENTOS DEL ÍNDICE:
{index_context}

DOCUMENTOS CARGADOS POR EL USUARIO:
{user_context}

PREGUNTA:
{request.question}
"""

    client = AIServices.chat_client()

    completion = client.chat.completions.create(
        model=settings.ai_services.chat_deployment,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0
    )

    return {
        "answer": completion.choices[0].message.content,
        "citations": citations
    }
