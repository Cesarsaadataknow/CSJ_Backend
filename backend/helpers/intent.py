def should_generate_document(question: str) -> bool:
    triggers = [
        "redacta",
        "genera",
        "providencia",
        "decisión",
        "auto",
        "sentencia",
        "documento",
        "word",
    ]

    q = question.lower()
    return any(t in q for t in triggers)
