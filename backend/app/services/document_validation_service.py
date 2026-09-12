from dataclasses import dataclass

from app.core.config import settings


SUPPORTED_TYPES = {"application/pdf", "image/jpeg", "image/png"}
EXTENSION_TYPES = {".pdf": "application/pdf", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png"}


@dataclass
class FileValidation:
    file_type: str
    is_supported: bool
    is_readable: bool
    page_count: int
    status: str
    error_code: str | None = None
    error_message: str | None = None

    def as_dict(self) -> dict:
        return {
            "file_type": self.file_type,
            "is_supported": self.is_supported,
            "is_readable": self.is_readable,
            "page_count": self.page_count,
            "status": self.status,
        }


def validate_file(filename: str, content: bytes) -> FileValidation:
    suffix = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    file_type = EXTENSION_TYPES.get(suffix, "application/octet-stream")
    if file_type not in SUPPORTED_TYPES:
        return FileValidation(file_type, False, False, 0, "FAILED", "UNSUPPORTED_FILE_TYPE", "Only PDF / JPG / PNG documents are supported.")
    if not content:
        return FileValidation(file_type, True, False, 0, "FAILED", "EMPTY_FILE", "The uploaded file is empty.")
    if len(content) > settings.max_file_size_mb * 1024 * 1024:
        return FileValidation(file_type, True, False, 0, "FAILED", "FILE_TOO_LARGE", "The uploaded file exceeds the size limit.")
    try:
        if file_type == "application/pdf":
            from pypdf import PdfReader
            import io
            page_count = len(PdfReader(io.BytesIO(content)).pages)
        else:
            from PIL import Image
            import io
            with Image.open(io.BytesIO(content)) as image:
                image.verify()
            page_count = 1
    except Exception:
        return FileValidation(file_type, True, False, 0, "FAILED", "UNREADABLE_FILE", "The uploaded file could not be read.")
    if page_count > 3:
        return FileValidation(file_type, True, True, page_count, "FAILED", "PAGE_LIMIT_EXCEEDED", "Documents may contain no more than 3 pages.")
    return FileValidation(file_type, True, True, page_count, "PASS")
