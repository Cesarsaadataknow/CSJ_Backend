from docx import Document
from io import BytesIO
from azure.identity import DefaultAzureCredential
from azure.storage.filedatalake import DataLakeServiceClient


def _replace_placeholder(container, placeholder: str, value: str):
    for paragraph in container.paragraphs:
        if placeholder in paragraph.text:
            for run in paragraph.runs:
                if placeholder in run.text:
                    run.text = run.text.replace(placeholder, value or "")

    for table in container.tables:
        for row in table.rows:
            for cell in row.cells:
                _replace_placeholder(cell, placeholder, value)


def generate_word(template_path: str, content: dict) -> bytes:
    doc = Document(template_path)

    replacements = {
        "{{ANTECEDENTES}}": content.get("antecedentes", ""),
        "{{ACTUACION_PROCESAL}}": content.get("actuacion_procesal", ""),
        "{{ARGUMENTOS_PARTES}}": content.get("argumentos_partes", ""),
        "{{CONSIDERACIONES}}": content.get("consideraciones", ""),
        "{{DECISION}}": content.get("decision", ""),
        "{{RECOMENDACIONES_IA}}": content.get("recomendaciones_ia", ""),
    }

    for placeholder, value in replacements.items():
        _replace_placeholder(doc, placeholder, value.strip())

    buffer = BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer.read()


def upload_to_onelake(
    workspace_name: str,
    lakehouse_name: str,
    folder: str,
    filename: str,
    content_bytes: bytes
) -> str:

    service = DataLakeServiceClient(
        account_url="https://onelake.dfs.fabric.microsoft.com",
        credential=DefaultAzureCredential()
    )

    fs = service.get_file_system_client(workspace_name)
    dir_path = f"{lakehouse_name}.Lakehouse/Files/{folder}".rstrip("/")
    dir_client = fs.get_directory_client(dir_path)

    try:
        dir_client.create_directory()
    except Exception:
        pass

    file_client = dir_client.get_file_client(filename)
    file_client.upload_data(BytesIO(content_bytes), overwrite=True)

    return f"{lakehouse_name}.Lakehouse/Files/{folder}/{filename}"


# from docx import Document
# from pathlib import Path
# from io import BytesIO
# from azure.identity import DefaultAzureCredential
# from azure.storage.filedatalake import DataLakeServiceClient

# ORDER = [
#     ("I. ANTECEDENTES", "antecedentes"),
#     ("II. CONSIDERACIONES", "consideraciones"),
#     ("III. PROBLEMA JURÍDICO", "problema"),
#     ("IV. DECISIÓN", "decision"),
# ]

# def generate_word(template_path: str, content: dict)-> bytes:
#     # Cargar plantilla (solo títulos o incluso vacía)
#     doc = Document(template_path)

#     # Borrar TODO el contenido existente
#     doc._body.clear_content()

#     for title, key in ORDER:
#         # Título
#         p_title = doc.add_paragraph()
#         run = p_title.add_run(title)
#         run.bold = True

#         # Texto generado
#         p_body = doc.add_paragraph()
#         p_body.add_run(content.get(key, "").strip())

#         # Espacio entre secciones
#         doc.add_paragraph()

#     buffer = BytesIO()
#     doc.save(buffer)
#     buffer.seek(0)
#     return buffer.read()



# def upload_to_onelake(
#     workspace_name: str,
#     lakehouse_name: str,
#     folder: str,
#     filename: str,
#     content_bytes: bytes) -> str:
    
#     service = DataLakeServiceClient(
#         account_url="https://onelake.dfs.fabric.microsoft.com",
#         credential=DefaultAzureCredential()
#     )

#     fs = service.get_file_system_client(workspace_name)  # filesystem = WORKSPACE
#     dir_path = f"{lakehouse_name}.Lakehouse/Files/{folder}".rstrip("/")
#     dir_client = fs.get_directory_client(dir_path)

#     # crear carpeta si no existe
#     try:
#         dir_client.create_directory()
#     except Exception:
#         pass

#     file_client = dir_client.get_file_client(filename)
#     file_client.upload_data(BytesIO(content_bytes), overwrite=True)

#     return f"{lakehouse_name}.Lakehouse/Files/{folder}/{filename}"
