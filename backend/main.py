from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.chats import chat_router 
from api.chats import download_router as download
from api import auth

app = FastAPI(
    title="Agente Jurídico - Resolución de Conflictos",
    version="0.1.1"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat_router)
app.include_router(auth.router, prefix="/api/auth",tags=["auth"])
app.include_router(download)








# from fastapi import FastAPI
# from fastapi.middleware.cors import CORSMiddleware
# from helpers.chat import chat_router, download_router
# from api import auth

# app = FastAPI(
#     title="Agente Jurídico - Resolución de Conflictos",
#     version="0.1.0"
# )

# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# app.include_router(
#     chat_router,
#     prefix="/api/chat",
#     tags=["chat"]
# )

# app.include_router(
#     auth.router,
#     prefix="/api/auth", 
#     tags=["auth"]
#     )

# app.include_router(
#     download_router, 
#     prefix="/api",
#     )


