import re
from typing import Any, Callable, Optional
import io
from azure.core.credentials import AzureKeyCredential
from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.ai.documentintelligence.models import (
    AnalyzeDocumentRequest,
    DocumentAnalysisFeature,
)

from app.config import settings


class DocumentIntelligenceExtractor:
    def __init__(
        self,
        vision_callback: Optional[Callable[[bytes, int], str]] = None,
    ) -> None:
        self.client = DocumentIntelligenceClient(
            endpoint=settings.AZURE_FORM_RECOGNIZER_ENDPOINT,
            credential=AzureKeyCredential(settings.AZURE_FORM_RECOGNIZER_API_KEY),
        )
        self.vision_callback = vision_callback

    def extract_document(self, file_bytes: bytes, content_type: str) -> dict[str, Any]:
        if not file_bytes:
            raise ValueError("file_bytes llegó vacío")

        if content_type == "application/pdf" and not file_bytes.startswith(b"%PDF"):
            raise ValueError("El archivo no parece ser un PDF válido")
        
        poller = self.client.begin_analyze_document(
            model_id="prebuilt-layout",
            body=io.BytesIO(file_bytes),
            content_type="application/pdf",
        )
        result = poller.result()

        pages_output: list[dict[str, Any]] = []
        full_text_parts: list[str] = []

        tables_by_page: dict[int, list[dict[str, Any]]] = {}
        paragraphs_by_page: dict[int, list[str]] = {}
        figures_by_page: dict[int, list[str]] = {}

        # ----------------------------
        # TABLAS
        # ----------------------------
        if getattr(result, "tables", None):
            for idx, table in enumerate(result.tables, start=1):
                page_number = self._get_table_page_number(table)

                is_complex = self._is_complex_table(table)
                needs_ai_table = self._needs_ai_for_table(table)

                if is_complex:
                    table_text = self._table_to_structured_text(table, idx)
                    table_type = "complex"
                else:
                    table_text = self._table_to_markdown(table, idx)
                    table_type = "simple"

                if table_text:
                    tables_by_page.setdefault(page_number, []).append(
                        {
                            "table_index": idx,
                            "table_type": table_type,
                            "needs_ai": needs_ai_table,
                            "text": table_text,
                            "row_count": table.row_count or 0,
                            "column_count": table.column_count or 0,
                        }
                    )

        # ----------------------------
        # PÁRRAFOS
        # ----------------------------
        if getattr(result, "paragraphs", None):
            for paragraph in result.paragraphs:
                text = (getattr(paragraph, "content", "") or "").strip()
                if not text:
                    continue

                role = getattr(paragraph, "role", None)
                if role:
                    text = f"[{str(role).upper()}]\n{text}"

                page_number = self._get_paragraph_page_number(paragraph)
                paragraphs_by_page.setdefault(page_number, []).append(text)

        # ----------------------------
        # FIGURAS / INFOGRAMAS
        # ----------------------------
        if getattr(result, "figures", None):
            for idx, figure in enumerate(result.figures, start=1):
                page_number = self._get_figure_page_number(figure)
                figure_text = self._figure_to_text(figure, idx)
                if figure_text:
                    figures_by_page.setdefault(page_number, []).append(figure_text)

        # ----------------------------
        # PÁGINAS
        # ----------------------------
        if getattr(result, "pages", None):
            for page in result.pages:
                page_number = page.page_number

                page_lines: list[str] = []
                page_paragraphs = paragraphs_by_page.get(page_number, [])
                page_tables_payload = tables_by_page.get(page_number, [])
                page_figures = figures_by_page.get(page_number, [])

                page_tables_text = [t["text"] for t in page_tables_payload]

                # Preferimos paragraphs; si no, lines
                if page_paragraphs:
                    page_lines.extend(page_paragraphs)
                elif getattr(page, "lines", None):
                    for line in page.lines:
                        t = (line.content or "").strip()
                        if t:
                            page_lines.append(t)

                page_content_parts: list[str] = []

                if page_lines:
                    page_text = "\n".join(page_lines).strip()
                    if page_text:
                        page_content_parts.append("[TEXTO]\n" + page_text)

                if page_tables_text:
                    page_content_parts.append("\n\n".join(page_tables_text))

                if page_figures:
                    page_content_parts.append("\n\n".join(page_figures))

                page_content = "\n\n".join(page_content_parts).strip()

                page_needs_ai, ai_reason = self._needs_ai_review(
                    page_text=page_content,
                    table_payloads=page_tables_payload,
                    figure_count=len(page_figures),
                )

                visual_description = ""
                if page_needs_ai and self.vision_callback is not None:
                    try:
                        visual_description = (
                            self.vision_callback(file_bytes, page_number) or ""
                        ).strip()
                    except Exception:
                        visual_description = ""

                if visual_description:
                    page_content = (
                        f"{page_content}\n\n[DESCRIPCIÓN_VISUAL]\n{visual_description}"
                    ).strip()

                pages_output.append(
                    {
                        "page_number": page_number,
                        "text": page_content,
                        "paragraphs": page_paragraphs,
                        "tables": page_tables_payload,
                        "figures": page_figures,
                        "needs_ai": page_needs_ai,
                        "ai_reason": ai_reason,
                        "visual_description": visual_description,
                    }
                )

                if page_content:
                    full_text_parts.append(f"[PÁGINA {page_number}]\n{page_content}")

        # ----------------------------
        # FALLBACK
        # ----------------------------
        if not full_text_parts and getattr(result, "paragraphs", None):
            fallback_parts = []
            for paragraph in result.paragraphs:
                t = (getattr(paragraph, "content", "") or "").strip()
                if t:
                    fallback_parts.append(t)
            if fallback_parts:
                full_text_parts.append("\n".join(fallback_parts))

        return {
            "content": "\n\n".join(full_text_parts).strip(),
            "pages": pages_output,
            "metadata": {
                "page_count": len(getattr(result, "pages", []) or []),
                "tables_count": len(getattr(result, "tables", []) or []),
                "paragraphs_count": len(getattr(result, "paragraphs", []) or []),
                "figures_count": len(getattr(result, "figures", []) or []),
                "pages_marked_for_ai": sum(1 for p in pages_output if p["needs_ai"]),
                "tables_marked_for_ai": sum(
                    1
                    for p in pages_output
                    for t in p.get("tables", [])
                    if t.get("needs_ai")
                ),
            },
        }

    def extract_text(self, file_bytes: bytes, content_type: str) -> str:
        document = self.extract_document(file_bytes, content_type)
        return document["content"]

    # =========================================================
    # TABLAS
    # =========================================================
    def _is_complex_table(self, table) -> bool:
        if not getattr(table, "cells", None):
            return False

        if (table.column_count or 0) >= 8:
            return True

        for cell in table.cells:
            if (getattr(cell, "column_span", 1) or 1) > 1:
                return True
            if (getattr(cell, "row_span", 1) or 1) > 1:
                return True

        return False

    def _needs_ai_for_table(self, table) -> bool:
        if not getattr(table, "cells", None):
            return False

        col_count = table.column_count or 0
        row_count = table.row_count or 0

        if col_count >= 10:
            return True

        if row_count >= 20 and col_count >= 6:
            return True

        span_count = 0
        for cell in table.cells:
            if (getattr(cell, "column_span", 1) or 1) > 1:
                span_count += 1
            if (getattr(cell, "row_span", 1) or 1) > 1:
                span_count += 1

        if span_count >= 4:
            return True

        return False

    def _table_to_markdown(self, table, index: int) -> str:
        if not getattr(table, "cells", None):
            return ""

        row_count = table.row_count or 0
        col_count = table.column_count or 0

        matrix = [["" for _ in range(col_count)] for _ in range(row_count)]

        for cell in table.cells:
            row_index = cell.row_index or 0
            col_index = cell.column_index or 0
            content = (cell.content or "").strip()

            if row_index < row_count and col_index < col_count:
                matrix[row_index][col_index] = content

        if not matrix:
            return ""

        lines = [f"[TABLA {index} - SIMPLE]"]

        for i, row in enumerate(matrix):
            safe_row = [self._clean_cell_text(cell) for cell in row]
            lines.append("| " + " | ".join(safe_row) + " |")

            if i == 0:
                lines.append("| " + " | ".join(["---"] * len(safe_row)) + " |")

        return "\n".join(lines).strip()

    def _table_to_structured_text(self, table, index: int) -> str:
        """
        Para tablas complejas con subcolumnas, spans y muchas columnas.
        Conserva mejor la semántica para RAG que un markdown plano.
        """
        if not getattr(table, "cells", None):
            return ""

        row_count = table.row_count or 0
        col_count = table.column_count or 0

        # matriz expandida con soporte de spans
        matrix = [[[] for _ in range(col_count)] for _ in range(row_count)]

        for cell in table.cells:
            r = cell.row_index or 0
            c = cell.column_index or 0
            row_span = getattr(cell, "row_span", 1) or 1
            col_span = getattr(cell, "column_span", 1) or 1
            content = self._clean_cell_text((cell.content or "").strip())

            for rr in range(r, min(r + row_span, row_count)):
                for cc in range(c, min(c + col_span, col_count)):
                    matrix[rr][cc].append(content)

        lines = [f"[TABLA {index} - ESTRUCTURA_COMPLEJA]"]
        lines.append(f"[DIMENSIONES] filas={row_count}, columnas={col_count}")

        # heurística: las primeras 2 filas suelen ser encabezados si es tabla compleja
        header_rows = min(2, row_count)

        for i in range(header_rows):
            row_values = []
            for j in range(col_count):
                joined = self._join_unique(matrix[i][j])
                row_values.append(joined)
            lines.append(f"[HEADER_ROW_{i + 1}] " + " | ".join(row_values))

        for i in range(header_rows, row_count):
            row_values = []
            for j in range(col_count):
                joined = self._join_unique(matrix[i][j])
                row_values.append(joined)
            lines.append(f"[ROW_{i - header_rows + 1}] " + " | ".join(row_values))

        return "\n".join(lines).strip()

    def _join_unique(self, values: list[str]) -> str:
        if not values:
            return ""
        unique_values = list(dict.fromkeys(v for v in values if v))
        return " / ".join(unique_values)

    # =========================================================
    # FIGURAS
    # =========================================================
    def _figure_to_text(self, figure, index: int) -> str:
        parts = [f"[FIGURA {index}]"]

        caption_obj = getattr(figure, "caption", None)
        caption = ""
        if caption_obj:
            caption = (getattr(caption_obj, "content", "") or "").strip()

        if caption:
            parts.append(f"[CAPTION]\n{caption}")
        else:
            parts.append("[CAPTION]\nFigura detectada sin caption claro.")

        return "\n".join(parts).strip()

    # =========================================================
    # DETECCIÓN DE IA
    # =========================================================
    def _needs_ai_review(
        self,
        page_text: str,
        table_payloads: list[dict[str, Any]],
        figure_count: int,
    ) -> tuple[bool, str]:
        text = (page_text or "").strip()

        if not text:
            return True, "Página sin texto útil"

        if figure_count > 0:
            return True, "Página con figuras o infogramas"

        if len(text) < 120:
            return True, "Muy poco texto extraído"

        weird_ratio = self._compute_weird_ratio(text)
        if weird_ratio > 0.18:
            return True, "Texto con señales de OCR pobre"

        short_words = sum(1 for w in text.split() if len(w) == 1)
        if short_words > 25:
            return True, "Muchas palabras cortas por OCR defectuoso"

        complex_tables = [t for t in table_payloads if t.get("table_type") == "complex"]
        ai_tables = [t for t in table_payloads if t.get("needs_ai")]

        if len(complex_tables) >= 1 and len(text.split()) < 100:
            return True, "Página con tabla compleja"

        if len(ai_tables) >= 1:
            return True, "Página con tabla muy compleja para análisis adicional"

        return False, ""

    def _compute_weird_ratio(self, text: str) -> float:
        if not text:
            return 1.0

        weird_chars = 0
        allowed = set(".,;:()[]{}%$#/-_+*@¡!¿?=<>|\\\"'áéíóúÁÉÍÓÚñÑ")

        for ch in text:
            if ch.isalnum() or ch.isspace() or ch in allowed:
                continue
            weird_chars += 1

        return weird_chars / max(len(text), 1)

    # =========================================================
    # HELPERS
    # =========================================================
    def _clean_cell_text(self, text: str) -> str:
        text = re.sub(r"\s+", " ", text or "").strip()
        return text.replace("|", "/")

    def _get_paragraph_page_number(self, paragraph) -> int:
        bounding_regions = getattr(paragraph, "bounding_regions", None) or []
        if bounding_regions:
            return bounding_regions[0].page_number
        return 1

    def _get_table_page_number(self, table) -> int:
        bounding_regions = getattr(table, "bounding_regions", None) or []
        if bounding_regions:
            return bounding_regions[0].page_number
        return 1

    def _get_figure_page_number(self, figure) -> int:
        bounding_regions = getattr(figure, "bounding_regions", None) or []
        if bounding_regions:
            return bounding_regions[0].page_number
        return 1


class TextCleaner:
    def clean(self, text: str) -> str:
        text = (text or "").strip()
        if not text:
            return ""

        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)

        lines = [line.strip() for line in text.splitlines()]
        cleaned_lines = []
        previous_blank = False

        for line in lines:
            is_blank = not line
            if is_blank and previous_blank:
                continue
            cleaned_lines.append(line)
            previous_blank = is_blank

        return "\n".join(cleaned_lines).strip()