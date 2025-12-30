def build_identity_check_prompt(context: str) -> str:
    return f"""
Analiza el siguiente contexto jurídico.

1. Enumera TODOS los sujetos procesales mencionados.
2. Indica si existe riesgo de confusión de identidad.
3. Si hay más de un sujeto principal o homónimos, indícalo claramente.

CONTEXTO:
{context}

Devuelve SOLO:
- SUJETOS IDENTIFICADOS:
- ¿RIESGO DE CONFUSIÓN?: SÍ / NO
- OBSERVACIÓN:
"""
