# Nova Trade Document Validation POC

## What this POC is about

This POC validates trade documents using a 3-agent pipeline:
- Extractor Agent: extracts required shipment fields from uploaded documents with confidence scores.
- Validator Agent: checks extracted fields against customer rules and marks each field as match, mismatch, or uncertain.
- Router Agent: returns a final decision (`auto_approve`, `human_review`, or `amendment_request`) with reasoning and a draft message.

The app includes a minimal UI to run the flow end-to-end and stores run results in SQLite so they can be queried later.

## How to run locally

1. Create and activate a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Optional (recommended) Gemini setup:

```bash
export GEMINI_API_KEY="your_key"
export GEMINI_MODEL="gemini-2.5-flash"
```

Or create a local `.env` file in project root:

```env
GEMINI_API_KEY=your_key
GEMINI_MODEL=gemini-2.5-flash
```

If no Gemini key is provided, the extractor fallback parser is used.

4. Start the app:

```bash
python run.py
```

5. Open in browser:

`http://127.0.0.1:8000`

## Samples used in this POC

Clean samples:
- [samples/clean/commercial_invoice_clean.txt](samples/clean/commercial_invoice_clean.txt)
- [samples/clean/bill_of_lading_clean.txt](samples/clean/bill_of_lading_clean.txt)
- [samples/clean/packing_list_clean.txt](samples/clean/packing_list_clean.txt)

Messy / low-quality sample:
- [samples/messy/commercial_invoice_messy.txt](samples/messy/commercial_invoice_messy.txt)
