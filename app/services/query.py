from __future__ import annotations

import re

from app.models import QueryResponse
from app.services.storage import Storage


class NLQueryService:
    def __init__(self, storage: Storage):
        self.storage = storage

    def ask(self, question: str) -> QueryResponse:
        normalized = question.strip().lower()

        if "flagged" in normalized and "week" in normalized:
            sql = (
                "SELECT COUNT(*) AS flagged_count FROM runs "
                "WHERE decision IN ('human_review', 'amendment_request') "
                "AND datetime(created_at) >= datetime('now', '-7 days')"
            )
            rows = self.storage.execute_query(sql)
            answer = f"Flagged shipments in last 7 days: {rows[0]['flagged_count']}"
            return QueryResponse(question=question, sql=sql, answer=answer, rows=rows)

        if "auto" in normalized and "approve" in normalized:
            sql = (
                "SELECT COUNT(*) AS auto_approved FROM runs "
                "WHERE decision = 'auto_approve' "
                "AND datetime(created_at) >= datetime('now', '-7 days')"
            )
            rows = self.storage.execute_query(sql)
            answer = f"Auto-approved shipments in last 7 days: {rows[0]['auto_approved']}"
            return QueryResponse(question=question, sql=sql, answer=answer, rows=rows)

        customer_match = re.search(r"customer\s+([a-z0-9_-]+)", normalized)
        if "pending" in normalized and customer_match:
            customer_id = customer_match.group(1)
            sql = (
                "SELECT run_id, created_at, decision FROM runs "
                "WHERE customer_id = ? AND decision IN ('human_review', 'amendment_request') "
                "ORDER BY created_at DESC"
            )
            rows = self.storage.execute_query(sql, (customer_id,))
            answer = f"Pending review items for customer {customer_id}: {len(rows)}"
            return QueryResponse(question=question, sql=sql, answer=answer, rows=rows)

        sql = "SELECT run_id, created_at, customer_id, decision FROM runs ORDER BY created_at DESC LIMIT 10"
        rows = self.storage.execute_query(sql)
        answer = "I could not map that question to a strict template. Showing recent runs."
        return QueryResponse(question=question, sql=sql, answer=answer, rows=rows)
