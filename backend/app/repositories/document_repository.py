import json
import sqlite3
from typing import List, Optional, Dict
from app.core.config import settings

class DocumentRepository:
    def __init__(self, db_path=None):
        self.db_path = db_path or settings.database_path

    def _connect(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """CREATE TABLE IF NOT EXISTS documents (
                    document_name TEXT PRIMARY KEY,
                    document_type TEXT NOT NULL,
                    processing_status TEXT NOT NULL,
                    processed_at TEXT NOT NULL,
                    result_json TEXT NOT NULL
                )"""
            )

    def save_result(self, result: dict) -> None:
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO documents(document_name, document_type, processing_status, processed_at, result_json)
                   VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(document_name) DO UPDATE SET
                     document_type=excluded.document_type,
                     processing_status=excluded.processing_status,
                     processed_at=excluded.processed_at,
                     result_json=excluded.result_json""",
                (
                    result["document_name"],
                    result["document_type"],
                    result["processing_status"],
                    result["processing_metadata"]["processed_at"],
                    json.dumps(result),
                ),
            )

    def list_results(self) -> List[Dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT document_name, document_type, processing_status, processed_at FROM documents ORDER BY processed_at DESC"
            ).fetchall()
        return [dict(row) for row in rows]

    def get_result(self, document_name: str) -> Optional[Dict]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT result_json FROM documents WHERE document_name = ?", (document_name,)
            ).fetchone()
        return json.loads(row["result_json"]) if row else None

repo = DocumentRepository()
