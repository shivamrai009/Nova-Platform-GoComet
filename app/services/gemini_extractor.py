from __future__ import annotations

import base64
import json
import os
import re
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import requests

TARGET_FIELDS = [
    "consignee_name",
    "hs_code",
    "port_of_loading",
    "port_of_discharge",
    "incoterms",
    "description_of_goods",
    "gross_weight",
    "invoice_number",
]

DEFAULT_MODEL = "gemini-2.5-flash"
MODEL_FALLBACKS = [
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "gemini-flash-latest",
]


class GeminiVisionExtractor:
    def __init__(self) -> None:
        self.api_key = os.getenv("GEMINI_API_KEY", "").strip()
        self.model = os.getenv("GEMINI_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    def extract(self, filename: str, content: bytes) -> dict[str, dict[str, Any]]:
        if not self.enabled:
            raise RuntimeError("GEMINI_API_KEY is not set")

        mime = guess_mime_type(filename)
        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": build_prompt()},
                        {
                            "inline_data": {
                                "mime_type": mime,
                                "data": base64.b64encode(content).decode("ascii"),
                            }
                        },
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0,
                "maxOutputTokens": 1200,
                "responseMimeType": "application/json",
            },
        }

        attempted_models = [self.model] + [m for m in MODEL_FALLBACKS if m != self.model]
        last_error: Exception | None = None
        body: dict[str, Any] | None = None

        for model_name in attempted_models:
            url = (
                f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent"
                f"?key={self.api_key}"
            )
            try:
                response = requests.post(url, json=payload, timeout=60)
                response.raise_for_status()
                body = response.json()
                break
            except requests.HTTPError as error:
                # Try the next candidate only when model name is invalid/unavailable.
                if response.status_code == 404:
                    last_error = error
                    continue
                raise RuntimeError(sanitize_error_message(error)) from error
            except Exception as error:
                raise RuntimeError(sanitize_error_message(error)) from error

        if body is None:
            raise RuntimeError(sanitize_error_message(last_error or RuntimeError("Unknown Gemini error")))

        text = extract_text_from_gemini_response(body)
        parsed = json.loads(strip_markdown_fence(text))
        normalized = normalize_output(parsed)
        return normalized


def sanitize_error_message(error: Exception) -> str:
    text = str(error)
    # Avoid persisting API keys in logs/warnings when request URLs are included in errors.
    text = re.sub(r"([?&]key=)[^&\s]+", r"\1[REDACTED]", text)
    for match in re.findall(r"https?://\S+", text):
        text = text.replace(match, sanitize_url(match))
    return text


def sanitize_url(url: str) -> str:
    parts = urlsplit(url)
    redacted_query = []
    for key, value in parse_qsl(parts.query, keep_blank_values=True):
        redacted_query.append((key, "[REDACTED]" if key.lower() == "key" else value))
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(redacted_query), parts.fragment))


def build_prompt() -> str:
    return (
        "You are extracting fields from a trade document. "
        "Return strict JSON only with this object shape: "
        "{\"fields\": {<field_name>: {\"value\": string|null, \"confidence\": number, \"evidence\": string|null}}}. "
        "Use confidence between 0 and 1. Do not hallucinate; use null when unknown. "
        "Required field names: "
        + ", ".join(TARGET_FIELDS)
    )


def guess_mime_type(filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix == ".pdf":
        return "application/pdf"
    if suffix in {".png"}:
        return "image/png"
    if suffix in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if suffix in {".webp"}:
        return "image/webp"
    return "text/plain"


def extract_text_from_gemini_response(payload: dict[str, Any]) -> str:
    candidates = payload.get("candidates", [])
    if not candidates:
        raise RuntimeError("Gemini returned no candidates")

    parts = candidates[0].get("content", {}).get("parts", [])
    for part in parts:
        text = part.get("text")
        if text:
            return text

    raise RuntimeError("Gemini response missing text content")


def strip_markdown_fence(text: str) -> str:
    candidate = text.strip()
    if candidate.startswith("```"):
        candidate = re.sub(r"^```(?:json)?\\s*", "", candidate)
        candidate = re.sub(r"\\s*```$", "", candidate)
    return candidate.strip()


def normalize_output(parsed: dict[str, Any]) -> dict[str, dict[str, Any]]:
    fields = parsed.get("fields", {}) if isinstance(parsed, dict) else {}
    output: dict[str, dict[str, Any]] = {}

    for name in TARGET_FIELDS:
        raw = fields.get(name, {}) if isinstance(fields, dict) else {}
        value = raw.get("value") if isinstance(raw, dict) else None
        evidence = raw.get("evidence") if isinstance(raw, dict) else None
        confidence = raw.get("confidence") if isinstance(raw, dict) else 0.0

        try:
            confidence_num = float(confidence)
        except (TypeError, ValueError):
            confidence_num = 0.0

        confidence_num = max(0.0, min(1.0, confidence_num))
        output[name] = {
            "value": None if value in ("", "null") else value,
            "confidence": confidence_num,
            "evidence": evidence,
        }

    return output
