# helpers/principal_function.py
from fastapi import UploadFile, HTTPException
from core.retrieval import retrieve_from_index
from core.ai_services import AIServices
from helpers.document_loader import extract_text_from_file
from helpers.prompts import build_prompt
from app.config import settings
from helpers.word_writer import generate_word, upload_to_onelake

cosmos_db = AIServices.AzureCosmosDB()

async def _process_chat(
    question: str,
    files: list[UploadFile] | None,
    session_id: str,
    user_id: str,
    mode: str = "providencia",
):
    if not user_id:
        raise HTTPException(status_code=401, detail="Usuario no autenticado.")
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id es requerido.")

    uploaded_files = []
    uploaded_text = ""

    if files:
        for file in files:
            extracted = extract_text_from_file(file)
            uploaded_text += f"\n\n[DOCUMENTO: {file.filename}]\n{extracted}"
            uploaded_files.append(file.filename)

    retrieved_docs = retrieve_from_index(question)

    index_context = ""
    citations = []
    retrieved_ids = []

    for i, d in enumerate(retrieved_docs, 1):
        texto = (d.get("texto") or "").strip()
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
            extra={"status": "no_context", "uploaded_files": uploaded_files},
        )
        return {"answer": answer, "citations": [], "session_id": session_id}

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

    if mode == "answer":
        completion = client.chat.completions.create(
            model=settings.AZURE_OPENAI_CHAT_DEPLOYMENT,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": build_prompt("RESPUESTA", full_context + f"\n\nPregunta: {question}\n")},
            ],
            temperature=0,
        )
        answer_text = completion.choices[0].message.content

        cosmos_db.save_answer_rag(
            session_id=session_id,
            user_id=user_id,
            user_question=question,
            ai_response=answer_text,
            citations=citations,
            file_path=None,
            channel="web",
            extra={
                "uploaded_files": uploaded_files,
                "retrieved_ids": retrieved_ids,
                "status": "ok_answer",
            },
        )
        return {"answer": answer_text, "citations": citations, "session_id": session_id}

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
        content=sections,
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
        content_bytes=docx_bytes,
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
        },
    )

    return {"answer": sections, "citations": citations, "file": onelake_dfs_url, "session_id": session_id}
