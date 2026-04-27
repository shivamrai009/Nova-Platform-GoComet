# Nova Trade Document Pipeline (POC)

This repository is scoped to the required DAW deliverables only.

## Deliverables Included

### Deliverable 1: PRD
- **Complete execution-oriented PRD** (7 sections, 3+ pages):
  - What Nova solves and why
  - FDE model and System of Outcomes context
  - Problem statement with specific failure modes
  - Personas (CG, SU) and 5 JTBDs
  - Agent architecture defense (why 3 agents)
  - LLM & tooling choices with tradeoffs
  - Trust, failure handling, and eval approach
  - Metrics (north-star + 5-8 supporting) and go/no-go criteria
- File: [docs/PRD-Complete.md](docs/PRD-Complete.md)
- Original minimal PRD: [docs/PRD-Part1.md](docs/PRD-Part1.md)

### Deliverable 2: UI Module
- One working CG screen showing four required states:
  - Incoming
  - Verification result
  - Discrepancy detail
  - Draft reply (editable, never auto-sent)
- Files:
  - ui/index.html
  - ui/assets/app.js
  - ui/assets/styles.css

### Deliverable 3: Working Wiring
- End-to-end chain implemented:
  1) Trigger (real ingest form or sample inbox simulation)
  2) Extract (multi-document)
  3) Cross-validate (including cross-document checks)
  4) Decide and draft
  5) Store and query
- Key files:
  - app/main.py
  - app/pipeline.py
  - app/agents/extractor.py
  - app/agents/validator.py
  - app/agents/router.py
  - app/services/storage.py
  - app/services/query.py

## Core Requirements Mapping (A-E)

### A) Extractor Agent
- Accepts trade docs and outputs required structured fields with confidence scores.
- Gemini vision-capable extractor is used when GEMINI_API_KEY is set.
- Files:
  - app/agents/extractor.py
  - app/services/gemini_extractor.py

### B) Validator Agent
- Produces per-field match/mismatch/uncertain.
- Includes found vs expected.
- Never silently approves uncertain fields.
- File: app/agents/validator.py

### C) Router Agent
- Outputs one of:
  - auto_approve
  - human_review
  - amendment_request
- Includes explicit reasoning and draft message.
- File: app/agents/router.py

### D) Storage + Query
- Stores verified outputs in SQLite.
- Supports basic NL questions over stored runs.
- Files:
  - app/services/storage.py
  - app/services/query.py

### E) Minimal UI
- Shows real run state from real pipeline execution.
- Displays extracted fields, confidence, validation, decision, reasoning, discrepancy detail, and editable draft.
- Files:
  - ui/index.html
  - ui/assets/app.js
  - ui/assets/styles.css

## Setup

1. Create and activate environment:

python -m venv .venv
source .venv/bin/activate

2. Install dependencies:

pip install -r requirements.txt

3. Optional Gemini setup:

export GEMINI_API_KEY="your_key"
export GEMINI_MODEL="gemini-2.5-flash"

Or create a local .env file at project root:

GEMINI_API_KEY=your_key
GEMINI_MODEL=gemini-2.5-flash

If GEMINI_API_KEY is not set, extractor fallback parsing is used.

## Run

Start app (default launcher behavior):

python run.py

Or explicit server command:

python run.py serve --reload --port 8000

Open:

http://127.0.0.1:8000

## Test and Demo

Run tests:

python run.py test

Run quick checks:

python run.py check

Run sample demo:

python run.py demo

## What to Upload in UI

Use trade-document samples from:
- samples/clean/commercial_invoice_clean.txt
- samples/clean/bill_of_lading_clean.txt
- samples/clean/packing_list_clean.txt
- samples/messy/commercial_invoice_messy.txt

Accepted file types:
- .pdf, .png, .jpg, .jpeg, .webp, .txt, .md, .csv

## Operator Demo Guide

For full walkthrough of backend flow, confidence logic, upload guidance, and validation checks, see:
- demo_guide.txt
