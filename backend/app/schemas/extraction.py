from typing import Optional, List, Dict, Any
from pydantic import BaseModel

class FieldEvidence(BaseModel):
    source_text: str
    page_number: int

class FieldValue(BaseModel):
    value: Optional[Any] = None
    confidence: Optional[float] = None
    page_number: Optional[int] = None
    evidence: Optional[FieldEvidence] = None

class LineItem(BaseModel):
    description: str
    quantity: Optional[float] = 1.0
    unit_price: Optional[float] = None
    amount: float

class ValidationCheck(BaseModel):
    name: str
    formula: str
    operands: Dict[str, Any]
    calculated_value: Optional[float] = None
    reported_value: Optional[float] = None
    variance: Optional[float] = None
    status: str

class ValidationSummary(BaseModel):
    checks: List[ValidationCheck]
    overall_status: str
    issues: List[str]
