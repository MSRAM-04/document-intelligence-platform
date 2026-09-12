from app.services.document_validation_service import validate_file


def test_rejects_unsupported_file():
    result = validate_file("notes.txt", b"hello")
    assert result.status == "FAILED"
    assert result.error_code == "UNSUPPORTED_FILE_TYPE"


def test_rejects_empty_file():
    result = validate_file("invoice.jpg", b"")
    assert result.status == "FAILED"
    assert result.error_code == "EMPTY_FILE"
