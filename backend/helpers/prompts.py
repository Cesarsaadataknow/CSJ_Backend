import re
from langchain.schema import HumanMessage

def build_prompt(section: str, context: str) -> str:
    return f"""
Eres un magistrado auxiliar de la Corte Suprema de Justicia de Colombia,
con experiencia en la resolución de conflictos de competencia.

Tu tarea es redactar EXCLUSIVAMENTE la siguiente sección de una providencia judicial:
{section}

════════════════════════════════════
INSTRUCCIONES JURÍDICAS
════════════════════════════════════
- Usa ÚNICAMENTE la información contenida en el contexto proporcionado.
- No inventes hechos, normas, fechas, autoridades ni decisiones.
- No hagas referencias a información externa ni a conocimientos generales.
- No hagas citas doctrinales ni jurisprudenciales distintas a las que aparezcan en el contexto.
- Si el contexto es insuficiente para desarrollar la sección solicitada,
  indícalo explícitamente de forma breve y objetiva.

════════════════════════════════════
ESTILO Y REDACCIÓN
════════════════════════════════════
- Lenguaje jurídico formal, técnico y preciso.
- Redacción clara, ordenada y coherente.
- Evita repeticiones innecesarias.
- Mantén un tono institucional y neutral.
- No incluyas introducciones ni conclusiones ajenas a la sección solicitada.

════════════════════════════════════
FORMATO
════════════════════════════════════
- Redacta el contenido en párrafos bien estructurados.
- Usa conectores jurídicos cuando sea pertinente.
- No incluyas encabezados distintos al nombre de la sección solicitada.
- No incluyas listas numeradas salvo que el contenido lo exija estrictamente.

════════════════════════════════════
CONTEXTO JURÍDICO DISPONIBLE
════════════════════════════════════
{context}
"""

def generate_session_title(llm, user_question: str) -> str:
    q = (user_question or "").strip()
    if not q:
        return "Nueva conversación"

    prompt = (
        "Genera un título MUY corto (2 a 3 palabras) para nombrar esta conversación.\n"
        "Reglas:\n"
        "- SOLO devuelve el título (sin comillas, sin punto final, sin emojis).\n"
        "- En español.\n"
        "- No incluyas números, cédulas, IDs, correos, teléfonos.\n"
        "- Evita nombres propios si no aportan.\n\n"
        f"Pregunta: {q}\n"
        "Título:"
    )

    try:
        resp = llm.invoke([HumanMessage(content=prompt)])
        title = (resp.content or "").strip()
    except Exception:
        title = "Nueva conversación"

    title = title.replace("\n", " ").strip()
    title = re.sub(r"[\"“”'`]", "", title)
    title = re.sub(r"\b\d+\b", "", title).strip()
    title = re.sub(r"\s+", " ", title).strip()
    title = title.rstrip(".")
    title = re.sub(r"[^\wáéíóúñüÁÉÍÓÚÑÜ\s-]", "", title).strip()

    # fuerza 2–6 palabras
    words = title.split()
    if len(words) < 2:
        return "Nueva conversación"
    if len(words) > 6:
        title = " ".join(words[:6])

    # límite UI
    if len(title) > 32:
        title = title[:32].rstrip()

    return title