from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from typing import Optional, List

from helpers.orchestrator import Orchestrator  

router = APIRouter(prefix="/api/chat", tags=["chat"])

orchestrator = Orchestrator()

ALLOWED_CT = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}

@router.post("/ask")
async def ask(
    question: str = Form(...),
    user_id: str = Form(...),
    session_id: str = Form(...),
):
    res = await orchestrator.ejecutar_agente(
        mensaje_usuario=question,
        user_id=user_id,
        session_id=session_id,
        files=None,
    )
    return res


@router.post("/upload")
async def upload(
    user_id: str = Form(...),
    session_id: str = Form(...),
    files: list[UploadFile] = File(...),
):
    # solo indexa, y responde confirmación
    res = await orchestrator.ejecutar_agente(
        mensaje_usuario="",     # vacío => “only_upload”
        user_id=user_id,
        session_id=session_id,
        files=files,
    )
    return res
