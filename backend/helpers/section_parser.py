def parse_sections(text: str) -> dict:
    sections = {
        "antecedentes": "",
        "problema": "",
        "consideraciones": "",
        "decision": "",
    }

    current = None
    for line in text.splitlines():
        l = line.upper()
        if "1. HECHOS" in l:
            current = "antecedentes"
        elif "3. PROBLEMA" in l:
            current = "problema"
        elif "4. CONSIDERACIONES" in l:
            current = "consideraciones"
        elif "5. DECISIÓN" in l:
            current = "decision"
        elif current:
            sections[current] += line + "\n"

    return sections
