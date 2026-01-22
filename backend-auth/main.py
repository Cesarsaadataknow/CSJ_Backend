
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.chat import chat_router
from api import auth
from core.ai_services import AIServices 
import time
import logging
from fastapi import Request

search_services = AIServices.AzureAiSearch()
app = FastAPI(title="SoftIA API Service")

# Middleware para medir y loguear el tiempo de cada petición
@app.middleware("http")
async def log_request_time(request: Request, call_next):
    start_time = time.perf_counter()
    response = await call_next(request)
    process_time = time.perf_counter() - start_time
    logging.info(f"Solicitud: {request.method} {request.url.path} completada en {process_time:.4f} segundos")
    return response

# Configura CORS para permitir peticiones del frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Registrar routers
app.include_router(chat_router, prefix="/api/chat", tags=["chat"])
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])

# Evento de inicio
@app.on_event("startup")
async def startup_event():
    # Eliminación de documentos obsoletos de Azure AI Search
    _ = await search_services.delete_old_documents()
    

    