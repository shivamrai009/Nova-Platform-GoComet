from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile  # pyright: ignore[reportMissingImports]
from fastapi.middleware.cors import CORSMiddleware  # pyright: ignore[reportMissingImports]
from fastapi.responses import FileResponse  # pyright: ignore[reportMissingImports]
from fastapi.staticfiles import StaticFiles  # pyright: ignore[reportMissingImports]

from app.config import BASE_DIR, DB_PATH, load_rules
from app.models import InboxAttachment, InboxIngestResponse, IncomingEmail
from app.pipeline import PipelineOrchestrator
from app.services.inbox import InboxService
from app.services.query import NLQueryService
from app.services.storage import Storage

app = FastAPI(title="Nova Trade Document Pipeline", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

storage = Storage(DB_PATH)
rules = load_rules()
orchestrator = PipelineOrchestrator(rules=rules)
query_service = NLQueryService(storage=storage)
inbox_service = InboxService()

UI_DIR = BASE_DIR / "ui"
app.mount("/assets", StaticFiles(directory=UI_DIR / "assets"), name="assets")


@app.get("/", include_in_schema=False)
def home() -> FileResponse:
    return FileResponse(UI_DIR / "index.html")


@app.post("/api/run")
async def run_pipeline(
    customer_id: str = Form(...),
    run_id: str | None = Form(default=None),
    files: list[UploadFile] = File(...),
) -> dict:
    if customer_id not in rules.get("customers", {}):
        raise HTTPException(status_code=400, detail=f"Unknown customer_id: {customer_id}")

    docs: list[tuple[str, bytes]] = []
    for file in files:
        docs.append((file.filename, await file.read()))

    run = orchestrator.run(customer_id=customer_id, documents=docs, run_id=run_id)
    storage.save_run(run)
    return run.model_dump(mode="json")


@app.get("/api/runs")
def list_runs() -> list[dict]:
    return storage.list_runs(limit=50)


@app.get("/api/runs/{run_id}")
def get_run(run_id: str) -> dict:
    payload = storage.get_run(run_id)
    if not payload:
        raise HTTPException(status_code=404, detail="Run not found")
    return payload


@app.get("/api/inbox/scenarios")
def list_inbox_scenarios() -> list[dict]:
    return [scenario.model_dump(mode="json") for scenario in inbox_service.list_scenarios()]


@app.post("/api/inbox/simulate/{scenario_id}")
def simulate_inbox(scenario_id: str) -> dict:
    try:
        response = inbox_service.simulate(scenario_id, orchestrator=orchestrator, storage=storage)
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return response.model_dump(mode="json")


@app.post("/api/inbox/ingest")
async def ingest_inbox_email(
    sender: str = Form(...),
    subject: str = Form(...),
    body: str = Form(...),
    customer_id: str = Form(...),
    run_id: str | None = Form(default=None),
    files: list[UploadFile] = File(...),
) -> dict:
    if customer_id not in rules.get("customers", {}):
        raise HTTPException(status_code=400, detail=f"Unknown customer_id: {customer_id}")

    docs: list[tuple[str, bytes]] = []
    attachments: list[InboxAttachment] = []
    for file in files:
        docs.append((file.filename, await file.read()))
        attachments.append(InboxAttachment(filename=file.filename))

    run = orchestrator.run(customer_id=customer_id, documents=docs, run_id=run_id)
    storage.save_run(run)

    incoming = IncomingEmail(
        sender=sender,
        subject=subject,
        body=body,
        customer_id=customer_id,
        attachments=attachments,
    )
    response = InboxIngestResponse(
        incoming_email=incoming,
        run=run,
        editable_draft_reply=run.decision.draft_message,
    )
    return response.model_dump(mode="json")


@app.get("/api/query")
def ask_query(q: str) -> dict:
    return query_service.ask(q).model_dump(mode="json")


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "db_path": str(DB_PATH), "ui": str(Path(UI_DIR))}


@app.on_event("shutdown")
def shutdown_event() -> None:
    orchestrator.close()
