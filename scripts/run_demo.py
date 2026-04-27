from __future__ import annotations

import json
from pathlib import Path

from app.config import load_rules
from app.services.inbox import InboxService
from app.pipeline import PipelineOrchestrator
from app.services.storage import Storage
from app.services.query import NLQueryService


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    rules = load_rules()
    orchestrator = PipelineOrchestrator(rules)
    storage = Storage(root / "data" / "nova_pipeline.db")
    inbox = InboxService()

    clean_docs = [
        root / "samples" / "clean" / "commercial_invoice_clean.txt",
        root / "samples" / "clean" / "bill_of_lading_clean.txt",
        root / "samples" / "clean" / "packing_list_clean.txt",
    ]
    messy_docs = [root / "samples" / "messy" / "commercial_invoice_messy.txt"]

    for group_name, docs in [("clean", clean_docs), ("messy", messy_docs)]:
        payload = [(path.name, path.read_bytes()) for path in docs]
        run = orchestrator.run(customer_id="acme_imports", documents=payload)
        storage.save_run(run)
        print(f"[{group_name}] run_id={run.run_id} decision={run.decision.decision}")

    print("\nSimulated inbox runs:")
    for scenario in inbox.list_scenarios():
        response = inbox.simulate(scenario.scenario_id, orchestrator=orchestrator, storage=storage)
        print(f"- {scenario.scenario_id}: {response.run.decision.decision} -> {response.run.decision.reasoning}")

    query = NLQueryService(storage)
    answer = query.ask("how many shipments were flagged this week?")
    print("\nQuery:", answer.question)
    print("Answer:", answer.answer)
    print("Rows:", json.dumps(answer.rows, indent=2))


if __name__ == "__main__":
    main()
