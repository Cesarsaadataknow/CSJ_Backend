#==================================================================================
import uuid
from fastapi import APIRouter, UploadFile, File, Form
from pydantic import BaseModel

from core.retrieval import retrieve_from_index
from core.ai_services import AIServices
from helpers.document_loader import extract_text_from_file
from helpers.word_writer import generate_word
from helpers.prompts import build_prompt
from app.config import settings
from helpers.intent import should_generate_document


# -----------------------------------------------------------------------------
# INICIALIZACIÓN
# -----------------------------------------------------------------------------
cosmos_db = AIServices.AzureCosmosDB()
chat_router = APIRouter(tags=["chat"])


# =============================================================================
# MODELO PARA JSON
# =============================================================================
class ChatJSONRequest(BaseModel):
    question: str
    session_id: str | None = None
    user_id: str | None = None


# =============================================================================
# UTILIDADES CONVERSACIONALES
# =============================================================================
def is_conversational_intent(question: str) -> str | None:
    q = question.lower().strip()

    greetings = [
        "hola", "buenos días", "buenas tardes",
        "buenas noches", "saludos", "hey"
    ]

    capabilities = [
        "qué puedes hacer", "que puedes hacer",
        "ayuda", "cómo funcionas", "como funcionas"
    ]

    if any(g in q for g in greetings):
        return "greeting"

    if any(c in q for c in capabilities):
        return "capabilities"

    return None


def conversational_response(intent: str) -> str:
    if intent == "greeting":
        return (
            "Hola 👋\n\n"
            "Soy un asistente jurídico especializado en la **resolución de conflictos "
            "de competencias** de la Corte Suprema de Justicia.\n\n"
            "Puedes consultarme sobre sentencias, criterios jurisprudenciales "
            "o cargar documentos para analizarlos."
        )

    if intent == "capabilities":
        return (
            "Puedo ayudarte con:\n\n"
            "- 📚 Análisis de sentencias sobre conflictos de competencia\n"
            "- 🧠 Identificación de criterios jurisprudenciales relevantes\n"
            "- 📝 Redacción estructurada de providencias\n"
            "- 📄 Análisis de documentos cargados (PDF o Word)\n\n"
            "Cuando quieras, formula tu consulta jurídica."
        )

    return ""


# =============================================================================
# ENDPOINTS
# =============================================================================
@chat_router.post("/")
async def chat(
    question: str = Form(...),
    session_id: str | None = Form(default=None),
    user_id: str | None = Form(default=None),
    files: list[UploadFile] | None = File(default=None)
):
    return await _process_chat(question, files, session_id, user_id)


@chat_router.post("/json")
async def chat_json(payload: ChatJSONRequest):
    return await _process_chat(
        payload.question,
        files=None,
        session_id=payload.session_id,
        user_id=payload.user_id
    )


@chat_router.post("/upload")
async def chat_upload(
    question: str = Form(...),
    session_id: str | None = Form(default=None),
    user_id: str | None = Form(default=None),
    files: list[UploadFile] = File(...)
):
    return await _process_chat(question, files, session_id, user_id)


# =============================================================================
# LÓGICA CENTRAL
# =============================================================================
async def _process_chat(
    question: str,
    files: list[UploadFile] | None,
    session_id: str | None,
    user_id: str | None
):
    # -------------------------------------------------
    # 0️⃣ Asegurar session_id
    # -------------------------------------------------
    if not session_id:
        session_id = str(uuid.uuid4())

    # -------------------------------------------------
    # 0.5️⃣ MODO CONVERSACIONAL
    # -------------------------------------------------
    intent = is_conversational_intent(question)
    if intent:
        answer = conversational_response(intent)

        cosmos_db.save_answer_rag(
            session_id=session_id,
            user_id=user_id,
            user_question=question,
            ai_response=answer,
            citations=[],
            file_path=None,
            channel="web",
            extra={"type": "conversational"}
        )

        return {
            "answer": answer,
            "citations": [],
            "session_id": session_id
        }

    # -------------------------------------------------
    # 1️⃣ Texto de documentos cargados
    # -------------------------------------------------
    uploaded_text = ""
    uploaded_files = []

    if files:
        for file in files:
            extracted = extract_text_from_file(file)
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

    if not index_context.strip() and not uploaded_text.strip():
        answer = "No se encontró información suficiente en el índice ni en los documentos cargados."

        cosmos_db.save_answer_rag(
            session_id=session_id,
            user_id=user_id,
            user_question=question,
            ai_response=answer,
            citations=[],
            file_path=None,
            channel="web",
            extra={"status": "no_context"}
        )

        return {
            "answer": answer,
            "citations": [],
            "session_id": session_id
        }

    # -------------------------------------------------
    # 3️⃣ Contexto unificado
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
    output_path = None

    if should_generate_document(question):
       output_path = "output/providencia_generada.docx"

    if output_path:  # doble seguridad
        generate_word(
            template_path="templates/providencia.docx",
            output_path=output_path,
            content=sections,
        )

    print("📄 Generar documento:", output_path)

    # output_path = "output/providencia_generada.docx"

    # generate_word(
    #     template_path="templates/providencia.docx",
    #     output_path=output_path,
    #     content=sections,
    # )

    # -------------------------------------------------
    # 7️⃣ Guardar en Cosmos
    # -------------------------------------------------
    cosmos_db.save_answer_rag(
        session_id=session_id,
        user_id=user_id,
        user_question=question,
        ai_response=sections,
        citations=citations,
        file_path=output_path,
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
        "file": output_path,
        "session_id": session_id,
    }
