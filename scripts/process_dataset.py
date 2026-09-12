"""Process every supplied dataset file through the same service used by the API."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.services.document_service import process_document


ROOT = Path(__file__).resolve().parents[2] / "New Dataset" / "New Dataset"
TYPES = {"Invoices": "invoice", "Balance Sheet": "balance_sheet", "Profit & Loss": "profit_and_loss", "Cash Flows": "cash_flow_statement"}


def main() -> None:
    output_dir = Path(__file__).resolve().parents[1] / "sample_outputs"
    output_dir.mkdir(exist_ok=True)
    for folder, document_type in TYPES.items():
        for path in sorted((ROOT / folder).iterdir()):
            if path.suffix.lower() not in {".pdf", ".jpg", ".jpeg", ".png"}:
                continue
            result = process_document(path.name, path.read_bytes(), document_type)
            destination = output_dir / f"{path.stem}.json"
            destination.write_text(json.dumps(result, indent=2), encoding="utf-8")
            print(f"{path.name}: {result['processing_status']}", flush=True)


if __name__ == "__main__":
    main()
