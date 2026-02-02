import json
import re
from dataclasses import dataclass
from typing import Literal, Optional
from langchain.schema import SystemMessage, HumanMessage, AIMessage
from langchain.schema import HumanMessage

def build_reasoning_prompt(context: str, question: str) -> str:
    return f"""
Actúas como Magistrado de la Corte Suprema de Justicia.

DEBES razonar siguiendo estrictamente este método:

1. HECHOS PROBADOS
2. IDENTIFICACIÓN DE LOS SUJETOS PROCESALES
3. PROBLEMA JURÍDICO
4. CONSIDERACIONES JURÍDICAS
5. DECISIÓN

REGLAS:
- No inventes hechos.
- No mezcles sujetos.
- Usa EXCLUSIVAMENTE el contenido del contexto.
- Si el contexto es insuficiente, decláralo.

CONTEXTO DOCUMENTAL:
{context}

PREGUNTA:
{question}

Devuelve el resultado con los títulos EXACTOS indicados.
"""