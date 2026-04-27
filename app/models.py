from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


DecisionType = Literal["auto_approve", "human_review", "amendment_request"]
ValidationStatus = Literal["match", "mismatch", "uncertain"]
RuleType = Literal["exact", "contains", "regex"]

REQUIRED_TRADE_FIELDS = (
    "consignee_name",
    "hs_code",
    "port_of_loading",
    "port_of_discharge",
    "incoterms",
    "description_of_goods",
    "gross_weight",
    "invoice_number",
)


class FieldExtraction(BaseModel):
    field: str
    value: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: str | None = None
    source_doc: str


class ExtractorFields(BaseModel):
    consignee_name: FieldExtraction
    hs_code: FieldExtraction
    port_of_loading: FieldExtraction
    port_of_discharge: FieldExtraction
    incoterms: FieldExtraction
    description_of_goods: FieldExtraction
    gross_weight: FieldExtraction
    invoice_number: FieldExtraction


class ExtractorOutput(BaseModel):
    doc_id: str
    doc_name: str
    doc_type: str
    extracted: ExtractorFields
    warnings: list[str] = Field(default_factory=list)


class ExtractionResult(BaseModel):
    doc_id: str
    doc_name: str
    doc_type: str
    fields: dict[str, FieldExtraction]
    warnings: list[str] = Field(default_factory=list)


class FieldRule(BaseModel):
    type: RuleType
    expected: str


class CustomerRules(BaseModel):
    min_confidence: float = Field(ge=0.0, le=1.0)
    field_rules: dict[str, FieldRule]


class RuleSet(BaseModel):
    customers: dict[str, CustomerRules]


class ValidationFieldResult(BaseModel):
    field: str
    status: ValidationStatus
    found: str | None = None
    expected: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str


class ValidationResult(BaseModel):
    customer_id: str
    overall_status: Literal["approved", "review", "amend"]
    field_results: dict[str, ValidationFieldResult]
    uncertain_fields: list[str]
    mismatches: list[str]
    cross_doc_issues: list[str] = Field(default_factory=list)


class DecisionResult(BaseModel):
    decision: DecisionType
    reasoning: str
    draft_message: str


class PipelineRun(BaseModel):
    run_id: str
    created_at: datetime
    customer_id: str
    extractions: list[ExtractionResult]
    validation: ValidationResult
    decision: DecisionResult


class QueryResponse(BaseModel):
    question: str
    sql: str
    answer: str
    rows: list[dict]


class InboxAttachment(BaseModel):
    filename: str
    path: str | None = None


class InboxScenario(BaseModel):
    scenario_id: str
    label: str
    sender: str
    subject: str
    body: str
    customer_id: str
    attachments: list[InboxAttachment]


class IncomingEmail(BaseModel):
    sender: str
    subject: str
    body: str
    customer_id: str
    attachments: list[InboxAttachment]


class InboxSimulationResponse(BaseModel):
    scenario: InboxScenario
    incoming_email: IncomingEmail
    run: PipelineRun
    editable_draft_reply: str


class InboxIngestResponse(BaseModel):
    incoming_email: IncomingEmail
    run: PipelineRun
    editable_draft_reply: str
