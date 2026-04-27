from __future__ import annotations

from app.models import DecisionResult, ValidationResult


class RouterAgent:
    name = "router"

    def run(self, validation: ValidationResult) -> DecisionResult:
        if validation.uncertain_fields:
            reasoning = (
                "At least one required field is missing or below confidence threshold; "
                "human review is mandatory to avoid silent approval."
            )
            draft = self._build_review_message(validation)
            return DecisionResult(decision="human_review", reasoning=reasoning, draft_message=draft)

        if validation.mismatches:
            reasoning = "Detected rule mismatches or cross-document inconsistencies; draft amendment request generated."
            draft = self._build_amendment_request(validation)
            return DecisionResult(decision="amendment_request", reasoning=reasoning, draft_message=draft)

        reasoning = "All required fields passed validation with sufficient confidence."
        draft = (
            "Subject: Document Set Approved\n\n"
            "All submitted trade documents have passed validation. Shipment can proceed."
        )
        return DecisionResult(decision="auto_approve", reasoning=reasoning, draft_message=draft)

    def _build_review_message(self, validation: ValidationResult) -> str:
        lines = [
            "Subject: Manual Review Required - Trade Documents",
            "",
            "The agent detected low-confidence fields and is escalating to CG for review:",
        ]
        for field in validation.uncertain_fields:
            item = validation.field_results[field]
            lines.append(f"- {field}: found '{item.found}', confidence={item.confidence:.2f}")
        lines.append("")
        lines.append("Please review source documents before responding to supplier.")
        return "\n".join(lines)

    def _build_amendment_request(self, validation: ValidationResult) -> str:
        lines = [
            "Subject: Amendment Required - Shipment Documents",
            "",
            "Hello Supplier Team,",
            "",
            "Please update the following discrepancies and re-submit the corrected documents:",
        ]

        for name, result in validation.field_results.items():
            if result.status == "mismatch":
                lines.append(
                    f"- {name}: found '{result.found}' | expected '{result.expected}'"
                )

        for issue in validation.cross_doc_issues:
            lines.append(f"- cross-document issue: {issue}")

        lines.extend([
            "",
            "Regards,",
            "Cargo Group",
        ])
        return "\n".join(lines)
