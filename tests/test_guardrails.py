from __future__ import annotations

from app.agents.router import RouterAgent
from app.models import ValidationFieldResult, ValidationResult
from app.services.gemini_extractor import sanitize_error_message


def build_validation(*, uncertain: list[str], mismatch: bool) -> ValidationResult:
    field = ValidationFieldResult(
        field="hs_code",
        status="mismatch" if mismatch else ("uncertain" if uncertain else "match"),
        found="8517.62" if mismatch else "8471.50",
        expected="^8471",
        confidence=0.91 if mismatch else (0.2 if uncertain else 0.95),
        reason="Expected exact value" if mismatch else "Low confidence or missing value",
    )
    return ValidationResult(
        customer_id="acme_imports",
        overall_status="review" if uncertain else ("amend" if mismatch else "approved"),
        field_results={"hs_code": field},
        uncertain_fields=uncertain,
        mismatches=["hs_code"] if mismatch else [],
        cross_doc_issues=[],
    )


def test_router_forces_human_review_on_uncertain_fields() -> None:
    router = RouterAgent()
    validation = build_validation(uncertain=["hs_code"], mismatch=False)

    result = router.run(validation)

    assert result.decision == "human_review"
    assert "mandatory" in result.reasoning.lower()


def test_router_builds_found_vs_expected_for_mismatch() -> None:
    router = RouterAgent()
    validation = build_validation(uncertain=[], mismatch=True)

    result = router.run(validation)

    assert result.decision == "amendment_request"
    assert "found '8517.62' | expected '^8471'" in result.draft_message


def test_error_redaction_hides_api_key() -> None:
    raw = (
        "404 Client Error: Not Found for url: "
        "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key=AIza1234567890abcd"
    )

    cleaned = sanitize_error_message(RuntimeError(raw))

    assert "AIza1234567890abcd" not in cleaned
    assert "REDACTED" in cleaned
