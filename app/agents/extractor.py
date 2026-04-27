from __future__ import annotations

import re
import uuid
from pathlib import Path

from app.models import ExtractionResult, FieldExtraction
from app.services.document_reader import extract_text_from_file
from app.services.gemini_extractor import GeminiVisionExtractor

REQUIRED_FIELDS = [
    "consignee_name",
    "hs_code",
    "port_of_loading",
    "port_of_discharge",
    "incoterms",
    "description_of_goods",
    "gross_weight",
    "invoice_number",
]

FIELD_PATTERNS: dict[str, list[str]] = {
    "consignee_name": [r"consignee(?: name)?\s*[:\-]\s*(.+)"],
    "hs_code": [r"hs(?: code)?\s*[:\-]\s*([0-9\.\-]+)"],
    "port_of_loading": [r"port of loading\s*[:\-]\s*(.+)"],
    "port_of_discharge": [r"port of discharge\s*[:\-]\s*(.+)"],
    "incoterms": [r"incoterms?\s*[:\-]\s*([A-Z]{3})"],
    "description_of_goods": [r"description(?: of goods)?\s*[:\-]\s*(.+)"],
    "gross_weight": [r"gross weight\s*[:\-]\s*([0-9\.,]+\s*[A-Za-z]+)"],
    "invoice_number": [r"invoice(?: number| no\.)?\s*[:\-]\s*([A-Za-z0-9\-_/]+)"],
}


class ExtractorAgent:
    """Extractor designed for deterministic local demos with confidence surfacing.

    In production this class should call a vision-capable LLM with structured output.
    """

    name = "extractor"

    def __init__(self) -> None:
        self.gemini = GeminiVisionExtractor()

    def run(self, filename: str, content: bytes) -> ExtractionResult:
        text = extract_text_from_file(filename, content)
        fields: dict[str, FieldExtraction] = {}
        warnings: list[str] = []
        doc_type = infer_doc_type(filename, text)

        gemini_values: dict[str, dict] | None = None
        if self.gemini.enabled:
            try:
                gemini_values = self.gemini.extract(filename=filename, content=content)
            except Exception as error:
                warnings.append(f"Gemini extraction failed, used fallback parser: {error}")

        for field in REQUIRED_FIELDS:
            if gemini_values and field in gemini_values:
                gemini_field = gemini_values[field]
                value = gemini_field.get("value")
                evidence = gemini_field.get("evidence")
                confidence = float(gemini_field.get("confidence", 0.0))
            else:
                value, evidence = find_field_value(field, text)
                if value:
                    confidence = confidence_from_signal(value, evidence)
                else:
                    confidence = 0.05
                    warnings.append(f"Missing field: {field}")

            fields[field] = FieldExtraction(
                field=field,
                value=value,
                confidence=confidence,
                evidence=evidence,
                source_doc=filename,
            )

        return ExtractionResult(
            doc_id=str(uuid.uuid4()),
            doc_name=Path(filename).name,
            doc_type=doc_type,
            fields=fields,
            warnings=warnings,
        )


def infer_doc_type(filename: str, text: str) -> str:
    lowered = f"{filename.lower()} {text.lower()}"
    if "bill of lading" in lowered or "bol" in lowered:
        return "bill_of_lading"
    if "packing list" in lowered:
        return "packing_list"
    if "invoice" in lowered:
        return "commercial_invoice"
    if "certificate of origin" in lowered:
        return "certificate_of_origin"
    return "unknown"


def find_field_value(field: str, text: str) -> tuple[str | None, str | None]:
    patterns = FIELD_PATTERNS.get(field, [])
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            value = normalize(match.group(1))
            return value, match.group(0).strip()
    return None, None


def normalize(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip(" .;:")


def confidence_from_signal(value: str, evidence: str | None) -> float:
    if not value:
        return 0.05
    if evidence and len(evidence) > 8:
        return 0.89
    return 0.75
