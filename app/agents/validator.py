from __future__ import annotations

import re

from app.models import ExtractionResult, ValidationFieldResult, ValidationResult


class ValidatorAgent:
    name = "validator"

    def run(self, customer_id: str, extractions: list[ExtractionResult], rules: dict) -> ValidationResult:
        merged_fields = self._merge_fields(extractions)
        field_rules = rules["customers"][customer_id]["field_rules"]
        min_confidence = rules["customers"][customer_id].get("min_confidence", 0.7)

        field_results: dict[str, ValidationFieldResult] = {}
        uncertain: list[str] = []
        mismatches: list[str] = []

        for field, rule in field_rules.items():
            extraction = merged_fields.get(field)
            found = extraction.get("value") if extraction else None
            conf = extraction.get("confidence", 0.0) if extraction else 0.0

            if not found or conf < min_confidence:
                field_results[field] = ValidationFieldResult(
                    field=field,
                    status="uncertain",
                    found=found,
                    expected=str(rule.get("expected", "")) if rule else None,
                    confidence=conf,
                    reason="Low confidence or missing value",
                )
                uncertain.append(field)
                continue

            status, reason = self._check_rule(found, rule)
            if status == "mismatch":
                mismatches.append(field)

            field_results[field] = ValidationFieldResult(
                field=field,
                status=status,
                found=found,
                expected=str(rule.get("expected", "")) if rule else None,
                confidence=conf,
                reason=reason,
            )

        cross_doc_issues = self._cross_validate(extractions)
        mismatches.extend([f"cross_doc::{issue}" for issue in cross_doc_issues])

        if uncertain:
            overall = "review"
        elif mismatches:
            overall = "amend"
        else:
            overall = "approved"

        return ValidationResult(
            customer_id=customer_id,
            overall_status=overall,
            field_results=field_results,
            uncertain_fields=uncertain,
            mismatches=mismatches,
            cross_doc_issues=cross_doc_issues,
        )

    def _check_rule(self, found: str, rule: dict) -> tuple[str, str]:
        rule_type = rule.get("type", "exact")
        expected = str(rule.get("expected", ""))

        if rule_type == "exact":
            if found.strip().lower() == expected.strip().lower():
                return "match", "Exact match"
            return "mismatch", "Expected exact value"

        if rule_type == "contains":
            if expected.lower() in found.lower():
                return "match", "Expected term present"
            return "mismatch", "Expected term missing"

        if rule_type == "regex":
            if re.search(expected, found, flags=re.IGNORECASE):
                return "match", "Regex matched"
            return "mismatch", "Regex mismatch"

        return "uncertain", "Unknown validation rule"

    def _merge_fields(self, extractions: list[ExtractionResult]) -> dict[str, dict]:
        merged: dict[str, dict] = {}
        for extraction in extractions:
            for field_name, field in extraction.fields.items():
                current = merged.get(field_name)
                if current is None or field.confidence > current["confidence"]:
                    merged[field_name] = {
                        "value": field.value,
                        "confidence": field.confidence,
                        "source_doc": field.source_doc,
                    }
        return merged

    def _cross_validate(self, extractions: list[ExtractionResult]) -> list[str]:
        checks = ["consignee_name", "hs_code"]
        issues: list[str] = []

        for field in checks:
            values: dict[str, set[str]] = {}
            for extraction in extractions:
                extracted = extraction.fields.get(field)
                if extracted and extracted.value:
                    normalized = extracted.value.strip().lower()
                    values.setdefault(normalized, set()).add(extraction.doc_name)

            if len(values) > 1:
                spread = "; ".join(
                    f"{value} -> {', '.join(sorted(names))}" for value, names in values.items()
                )
                issues.append(f"{field} inconsistent across docs: {spread}")

        return issues
