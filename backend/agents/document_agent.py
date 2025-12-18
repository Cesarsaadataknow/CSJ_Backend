import json
from openai import AzureOpenAI
from app.config import settings
from app.tools.fabric_search import search_jurisprudencia

client = AzureOpenAI(
    api_key=settings.AZURE_OPENAI_KEY,
    azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
    api_version=settings.AZURE_OPENAI_API_VERSION,
)

SYSTEM_PROMPT = """
Eres un asistente jurídico experto.
Debes elaborar un documento formal.

Estructura el contenido en:
- Antecedentes
- Análisis jurídico
- Decisión / Conclusiones

Cita explícitamente la jurisprudencia utilizada.
Devuelve SOLO JSON con las claves:
ANTECEDENTES, ANALISIS_JURIDICO, DECISION
"""

async def generate_document(instruction: str, user_text: str) -> dict:
    jurisprudencia = search_jurisprudencia(instruction)

    response = client.chat.completions.create(
        model=settings.AZURE_OPENAI_DEPLOYMENT,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"""
INSTRUCCIÓN:
{instruction}

DOCUMENTOS DEL USUARIO:
{user_text}

JURISPRUDENCIA:
{jurisprudencia}
"""}
        ],
        temperature=0.2
    )

    return json.loads(response.choices[0].message.content)
