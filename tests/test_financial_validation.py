from app.services.financial_validation_service import validate


def wrapped(**values):
    return {key: {"value": value} for key, value in values.items()}


def test_invoice_reconciles():
    result = validate("invoice", wrapped(subtotal=100, tax_amount=10, discount=0, total_amount=110))
    assert result["overall_status"] == "PASS"


def test_missing_inputs_are_not_applicable():
    result = validate("balance_sheet", wrapped(total_assets=100))
    assert result["checks"][0]["status"] == "NOT_APPLICABLE"
    assert result["overall_status"] == "NOT_APPLICABLE"
