import json
import asyncio

class Functions:

    def key_words(self, text: str) -> bool:
        t = (text or "").strip().lower()
        if not t:
            return True

        # mensajes típicos cuando solo suben archivo
        generic = {
            "adjunto", "te adjunto", "archivo", "archivos", "documento", "documentos",
            "revisa", "analiza", "por favor", "hola", "buenas", "ok", "listo", "ahi va",
            "aqui esta", "aquí está", "mira", "toma"
        }

        # si es muy corto y no tiene signos de pregunta/intención, lo tratamos como “solo subida”
        if len(t) <= 12 and t in generic:
            return True

        # si no hay ? y es muy corto, normalmente es “solo subida”
        if "?" not in t and len(t) < 18 and any(w in t for w in generic):
            return True

        return False



    async def llm_detect(self, text: str, llm) -> bool:
        t = (text or "").strip()
        if not t:
            return True

        prompt = f"""
    Devuelve SOLO JSON.

    {{"intent":"ONLY_UPLOAD"|"HAS_QUESTION"}}

    ONLY_UPLOAD = solo adjunta documentos sin pedir algo concreto.
    HAS_QUESTION = hay pregunta o tarea concreta (resumir, extraer, buscar, comparar, etc.)

    Mensaje:
    {t}
    """

        resp = await asyncio.to_thread(llm.invoke, prompt)
        raw = (getattr(resp, "content", "") or "").strip()

        try:
            data = json.loads(raw)
            return data.get("intent") == "ONLY_UPLOAD"
        except Exception:
            return False
