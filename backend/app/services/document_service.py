import time
from datetime import datetime, timezone

from app.core.database import save_result
from app.services.extraction_service import extract_document
from app.services.financial_validation_service import validate
from app.services.ocr_service import extract_text
from app.services.document_validation_service import validate_file

ANCHOR_FIELDS = {
    "invoice": ("total_amount", "invoice_number"),
    "balance_sheet": ("total_assets", "total_capital_and_liabilities"),
    "profit_and_loss": ("revenue", "gross_profit", "net_profit"),
    "cash_flow_statement": ("operating_cash_flow", "net_change_in_cash"),
    "cash_flow": ("operating_cash_flow", "net_change_in_cash"),
}

def process_document(filename: str, content: bytes, document_type: str) -> dict:
    started = time.perf_counter()
    file_validation = validate_file(filename, content)
    base = {"document_name": filename, "document_type": document_type, "file_validation": file_validation.as_dict()}
    
    if file_validation.status != "PASS":
        result = {
            **base,
            "processing_status": "FAILED",
            "extracted_data": {},
            "validation": {"checks": [], "overall_status": "NOT_APPLICABLE", "issues": [file_validation.error_code]},
            "processing_metadata": _metadata_empty(started)
        }
        return result

    extracted_text = extract_text(content, file_validation.file_type)
    if not extracted_text.text.strip():
        result = {
            **base,
            "processing_status": "FAILED",
            "extracted_data": {},
            "validation": {"checks": [], "overall_status": "NOT_APPLICABLE", "issues": ["OCR_FAILED"]},
            "processing_metadata": _metadata(extracted_text, started),
        }
        save_result(result)
        return result

    data = extract_document(document_type, extracted_text.text, extracted_text.pages)
    validation = validate(document_type, data)

    required_fields = ANCHOR_FIELDS.get(document_type, ())
    missing_required = [
        field for field in required_fields
        if not isinstance(data.get(field), dict) or data[field].get("value") is None
    ]
    processing_status = "PASS" if not missing_required else "FAILED"

    result = {
        **base,
        "processing_status": processing_status,
        "extracted_data": data,
        "validation": validation,
        "processing_metadata": {
            **_metadata(extracted_text, started),
            "missing_required_fields": missing_required,
        }
    }
    save_result(result)
    return result

def _metadata(extracted_text, started: float) -> dict:
    confidences = [value for value in extracted_text.page_confidences if value > 0]
    return {
        "ocr_used": extracted_text.ocr_used,
        "ocr_confidence": round(sum(confidences) / len(confidences), 2) if confidences else None,
        "processed_at": datetime.now(timezone.utc).isoformat(),
        "processing_time_ms": round((time.perf_counter() - started) * 1000, 2)
    }


def _metadata_empty(started: float) -> dict:
    return {
        "ocr_used": False,
        "ocr_confidence": None,
        "processed_at": datetime.now(timezone.utc).isoformat(),
        "processing_time_ms": round((time.perf_counter() - started) * 1000, 2),
    }
