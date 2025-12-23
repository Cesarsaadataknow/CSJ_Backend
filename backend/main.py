from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from helpers.chat import chat_router

app = FastAPI(
    title="Agente Jurídico - Resolución de Conflictos",
    version="0.1.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(
    chat_router,
    prefix="/api/chat",
    tags=["chat"]
)



# from fastapi import FastAPI
# from fastapi.middleware.cors import CORSMiddleware
# from helpers.chat import chat_router   # ← CAMBIO AQUÍ

# app = FastAPI(title="Agente Jurídico - Resolución de Conflictos")

# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# app.include_router(chat_router, prefix="/api/chat", tags=["chat"])
