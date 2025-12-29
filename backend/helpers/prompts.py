def build_prompt(section: str, context: str) -> str:
    return f"""
Eres un magistrado auxiliar de la Corte Suprema de Justicia.
Redacta únicamente la sección: {section}.

Reglas:
- Usa SOLO la información proporcionada
- Lenguaje jurídico formal
- No inventes hechos ni normas
- Redacción clara y estructurada

CONTEXTO:
{context}
"""
