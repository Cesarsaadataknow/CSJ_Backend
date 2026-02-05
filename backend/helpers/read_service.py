import re
from azure.core.credentials import AzureKeyCredential
from azure.ai.documentintelligence import DocumentIntelligenceClient
from app.config import settings

class DocumentIntelligenceExtractor:
    def __init__(self) -> None:
        self.client = DocumentIntelligenceClient(
            endpoint=settings.AZURE_FORM_RECOGNIZER_ENDPOINT,
            credential=AzureKeyCredential(settings.AZURE_FORM_RECOGNIZER_API_KEY),
        )

    def extract_text(self, file_bytes: bytes, content_type: str) -> str:
        poller = self.client.begin_analyze_document(
            model_id="prebuilt-layout",
            body=file_bytes,
            content_type=content_type,
        )
        result = poller.result()

        lines: list[str] = []

        if getattr(result, "pages", None):
            for page in result.pages:
                if getattr(page, "lines", None):
                    for line in page.lines:
                        t = (line.content or "").strip()
                        if t:
                            lines.append(t)

        if not lines and getattr(result, "paragraphs", None):
            for p in result.paragraphs:
                t = (p.content or "").strip()
                if t:
                    lines.append(t)

        return "\n".join(lines).strip()

class TextCleaner:
    def clean(self, text: str) -> str:
        text = (text or "").strip()
        if not text:
            return ""
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()