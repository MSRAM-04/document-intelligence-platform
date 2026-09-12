from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

class FileValidationSchema(BaseModel):
    file_type: str
    is_supported: bool
    is_readable: bool
    page_count: int
    status: str

class ProcessingMetadataSchema(BaseModel):
    ocr_used: bool
    ocr_confidence: Optional[float] = None
    processed_at: str
    processing_time_ms: float
    missing_required_fields: List[str] = Field(default_factory=list)

class DocumentResponseSchema(BaseModel):
    document_name: str
    document_type: str
    processing_status: str
    file_validation: FileValidationSchema
    extracted_data: Dict[str, Any]
    validation: Dict[str, Any]
    processing_metadata: ProcessingMetadataSchema

class DocumentListItemSchema(BaseModel):
    document_name: str
    document_type: str
    processing_status: str
    processed_at: str
