from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TypedDict

from langgraph.checkpoint.sqlite import SqliteSaver  # pyright: ignore[reportMissingImports]
from langgraph.graph import END, START, StateGraph  # pyright: ignore[reportMissingImports]

from app.config import GRAPH_CHECKPOINT_DB_PATH
from app.agents.extractor import ExtractorAgent
from app.agents.router import RouterAgent
from app.agents.validator import ValidatorAgent
from app.models import ExtractionResult, PipelineRun, ValidationResult


class PipelineState(TypedDict, total=False):
    run_id: str
    created_at: str
    customer_id: str
    documents: list[tuple[str, bytes]]
    extractions: list[dict[str, Any]]
    validation: dict[str, Any]
    decision: dict[str, Any]
    pipeline_run: dict[str, Any]


class PipelineOrchestrator:
    def __init__(self, rules: dict, checkpoint_db_path: Path | None = None):
        self.rules = rules
        self.extractor = ExtractorAgent()
        self.validator = ValidatorAgent()
        self.router = RouterAgent()
        db_path = checkpoint_db_path or GRAPH_CHECKPOINT_DB_PATH
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._checkpointer_cm = SqliteSaver.from_conn_string(str(db_path))
        self._checkpointer = self._checkpointer_cm.__enter__()
        self.graph = self._build_graph()

    def _build_graph(self):
        builder = StateGraph(PipelineState)
        builder.add_node("initialize", self._initialize_node)
        builder.add_node("extract", self._extract_node)
        builder.add_node("validate", self._validate_node)
        builder.add_node("route", self._route_node)
        builder.add_node("assemble", self._assemble_node)

        builder.add_edge(START, "initialize")
        builder.add_edge("initialize", "extract")
        builder.add_edge("extract", "validate")
        builder.add_edge("validate", "route")
        builder.add_edge("route", "assemble")
        builder.add_edge("assemble", END)
        return builder.compile(checkpointer=self._checkpointer)

    def _initialize_node(self, state: PipelineState) -> PipelineState:
        run_id = state.get("run_id") or str(uuid.uuid4())
        created_at = state.get("created_at") or datetime.now(timezone.utc).isoformat()
        return {"run_id": run_id, "created_at": created_at}

    def _extract_node(self, state: PipelineState) -> PipelineState:
        docs = state.get("documents", [])
        extractions = [
            self.extractor.run(filename, content).model_dump(mode="json")
            for filename, content in docs
        ]
        return {"extractions": extractions}

    def _validate_node(self, state: PipelineState) -> PipelineState:
        extraction_models = [
            ExtractionResult.model_validate(item) for item in state.get("extractions", [])
        ]
        validation = self.validator.run(
            customer_id=state["customer_id"],
            extractions=extraction_models,
            rules=self.rules,
        )
        return {"validation": validation.model_dump(mode="json")}

    def _route_node(self, state: PipelineState) -> PipelineState:
        validation = ValidationResult.model_validate(state["validation"])
        decision = self.router.run(validation=validation)
        return {"decision": decision.model_dump(mode="json")}

    def _assemble_node(self, state: PipelineState) -> PipelineState:
        payload = {
            "run_id": state["run_id"],
            "created_at": state["created_at"],
            "customer_id": state["customer_id"],
            "extractions": state["extractions"],
            "validation": state["validation"],
            "decision": state["decision"],
        }
        run = PipelineRun.model_validate(payload)
        return {"pipeline_run": run.model_dump(mode="json")}

    def run(self, customer_id: str, documents: list[tuple[str, bytes]], run_id: str | None = None) -> PipelineRun:
        state: PipelineState = {
            "customer_id": customer_id,
            "documents": documents,
        }
        if run_id:
            state["run_id"] = run_id

        thread_id = run_id or str(uuid.uuid4())
        config = {"configurable": {"thread_id": thread_id}}
        final_state = self.graph.invoke(state, config=config)
        return PipelineRun.model_validate(final_state["pipeline_run"])

    def close(self) -> None:
        self._checkpointer_cm.__exit__(None, None, None)
