from dataclasses import dataclass
from typing import Any, Optional

@dataclass
class DocumentRecord:
    document_name: str
    document_type: str
    processing_status: str
    processed_at: str
    result_json: dict
