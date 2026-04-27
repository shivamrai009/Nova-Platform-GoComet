from __future__ import annotations

import io
from pathlib import Path

from PIL import Image
from pypdf import PdfReader

try:
    import pytesseract
except Exception:  # pragma: no cover - optional OCR dependency
    pytesseract = None


def extract_text_from_file(filename: str, content: bytes) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix == ".pdf":
        return _extract_pdf_text(content)
    if suffix in {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}:
        return _extract_image_text(content)
    if suffix in {".txt", ".md", ".csv"}:
        return content.decode("utf-8", errors="ignore")

    # Fallback: treat unknown inputs as utf-8 text to keep the demo runnable.
    return content.decode("utf-8", errors="ignore")


def _extract_pdf_text(content: bytes) -> str:
    stream = io.BytesIO(content)
    reader = PdfReader(stream)
    pages: list[str] = []
    for page in reader.pages:
        pages.append(page.extract_text() or "")
    return "\n".join(pages)


def _extract_image_text(content: bytes) -> str:
    if pytesseract is None:
        return ""

    image = Image.open(io.BytesIO(content))
    return pytesseract.image_to_string(image)
