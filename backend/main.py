from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.chat import chat_router

app = FastAPI(title="Agente Jurídico – Resolución de Conflictos")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)

app.include_router(chat_router, prefix="/api/chat", tags=["chat"])
