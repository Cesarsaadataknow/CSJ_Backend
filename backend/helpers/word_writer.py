from docx import Document
from pathlib import Path

ORDER = [
    ("I. ANTECEDENTES", "antecedentes"),
    ("II. CONSIDERACIONES", "consideraciones"),
    ("III. PROBLEMA JURÍDICO", "problema"),
    ("IV. DECISIÓN", "decision"),
]

def generate_word(template_path: str, output_path: str, content: dict):
    # Cargar plantilla (solo títulos o incluso vacía)
    doc = Document(template_path)

    # Borrar TODO el contenido existente
    doc._body.clear_content()

    for title, key in ORDER:
        # Título
        p_title = doc.add_paragraph()
        run = p_title.add_run(title)
        run.bold = True

        # Texto generado
        p_body = doc.add_paragraph()
        p_body.add_run(content.get(key, "").strip())

        # Espacio entre secciones
        doc.add_paragraph()

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    doc.save(output_path)
