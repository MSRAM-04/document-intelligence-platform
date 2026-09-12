from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from app.core.database import get_result, list_results
from app.services.document_service import process_document

router = APIRouter(prefix="/documents", tags=["documents"])

@router.post("/process")
async def process(file: UploadFile = File(...), document_type: str = Form(...)) -> dict:
    allowed = {"invoice", "balance_sheet", "profit_and_loss", "cash_flow_statement", "cash_flow"}
    doc_type_clean = document_type.lower()
    if doc_type_clean not in allowed:
        raise HTTPException(status_code=422, detail=f"Unsupported document_type: {document_type}")

    try:
        content = await file.read()
        filename = file.filename or "unnamed_document"
        result = process_document(filename, content, doc_type_clean)
    except Exception as error:
        raise HTTPException(status_code=422, detail=f"Document processing failed: {str(error)}") from error

    if result["processing_status"] == "FAILED" and result.get("file_validation", {}).get("status") == "FAILED":
        code = result["validation"]["issues"][0] if result["validation"]["issues"] else "UNSUPPORTED_FILE_TYPE"
        messages = {
            "UNSUPPORTED_FILE_TYPE": "Only PDF / JPG / PNG documents are supported.",
            "EMPTY_FILE": "The uploaded file is empty.",
            "UNREADABLE_FILE": "The uploaded file could not be read.",
            "PAGE_LIMIT_EXCEEDED": "Documents may contain no more than 3 pages.",
            "FILE_TOO_LARGE": "The uploaded file exceeds the size limit.",
        }
        return JSONResponse(
            status_code=422,
            content={"error": {"code": code, "message": messages.get(code, "Document validation failed.")}}
        )

    return result

@router.get("")
def documents() -> list[dict]:
    return list_results()

@router.get("/{document_name}")
def document(document_name: str) -> dict:
    result = get_result(document_name)
    if result is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    return result
