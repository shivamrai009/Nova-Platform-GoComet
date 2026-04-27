from __future__ import annotations

import json
import os
from pathlib import Path

from app.models import RuleSet

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
RULES_FILE = DATA_DIR / "customer_rules.json"
DB_PATH = DATA_DIR / "nova_pipeline.db"
GRAPH_CHECKPOINT_DB_PATH = DATA_DIR / "langgraph_checkpoints.sqlite"
ENV_FILE = BASE_DIR / ".env"


def load_env_file(env_file: Path = ENV_FILE) -> None:
    if not env_file.exists():
        return

    for raw_line in env_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            continue

        if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
            value = value[1:-1]

        os.environ.setdefault(key, value)


# Load local .env once at startup so users do not need to export variables every session.
load_env_file()


def load_rules() -> dict:
    with RULES_FILE.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    # Parse with Pydantic to enforce a strict and predictable validator input contract.
    return RuleSet.model_validate(payload).model_dump(mode="json")
