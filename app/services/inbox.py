from __future__ import annotations

import json
from pathlib import Path

from app.config import BASE_DIR
from app.models import InboxScenario, InboxSimulationResponse, IncomingEmail
from app.pipeline import PipelineOrchestrator
from app.services.storage import Storage


class InboxService:
    def __init__(self, scenarios_path: Path | None = None):
        self.scenarios_path = scenarios_path or (BASE_DIR / "data" / "inbox_scenarios.json")
        self._scenarios = self._load_scenarios()

    def list_scenarios(self) -> list[InboxScenario]:
        return list(self._scenarios.values())

    def get_scenario(self, scenario_id: str) -> InboxScenario:
        scenario = self._scenarios.get(scenario_id)
        if scenario is None:
            raise KeyError(f"Unknown inbox scenario: {scenario_id}")
        return scenario

    def simulate(
        self,
        scenario_id: str,
        orchestrator: PipelineOrchestrator,
        storage: Storage,
    ) -> InboxSimulationResponse:
        scenario = self.get_scenario(scenario_id)
        docs: list[tuple[str, bytes]] = []
        for attachment in scenario.attachments:
            path = BASE_DIR / attachment.path
            docs.append((attachment.filename, path.read_bytes()))

        run = orchestrator.run(customer_id=scenario.customer_id, documents=docs)
        storage.save_run(run)

        incoming = IncomingEmail(
            sender=scenario.sender,
            subject=scenario.subject,
            body=scenario.body,
            customer_id=scenario.customer_id,
            attachments=scenario.attachments,
        )

        return InboxSimulationResponse(
            scenario=scenario,
            incoming_email=incoming,
            editable_draft_reply=run.decision.draft_message,
            run=run,
        )

    def _load_scenarios(self) -> dict[str, InboxScenario]:
        raw = json.loads(self.scenarios_path.read_text(encoding="utf-8"))
        scenarios: dict[str, InboxScenario] = {}
        for payload in raw["scenarios"]:
            scenario = InboxScenario(**payload)
            scenarios[scenario.scenario_id] = scenario
        return scenarios