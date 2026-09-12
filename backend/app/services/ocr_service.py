from __future__ import annotations

import io
import logging
from dataclasses import dataclass, field
from typing import List, Optional
import fitz # PyMuPDF
from PIL import Image, ImageEnhance, ImageFilter, ImageOps
from app.core.config import settings

logger = logging.getLogger(__name__)

def _preprocess_image(image: Image.Image) -> Image.Image:
    """Normalize scans while keeping OCR within Render request limits."""
    image = ImageOps.exif_transpose(image).convert("L")
    image = ImageOps.autocontrast(image)
    image = image.filter(ImageFilter.MedianFilter(size=3))
    max_dimension = max(image.size)
    if max_dimension > 2200:
        scale = 2200 / max_dimension
        image = image.resize((round(image.width * scale), round(image.height * scale)), Image.Resampling.LANCZOS)
    elif max_dimension < 1600:
        scale = 1600 / max_dimension
        image = image.resize((round(image.width * scale), round(image.height * scale)), Image.Resampling.LANCZOS)
    return ImageEnhance.Sharpness(image).enhance(1.5).convert("RGB")

@dataclass
class OCRWord:
    text: str
    confidence: float
    left: int
    top: int
    width: int
    height: int
    block_num: int = 0
    par_num: int = 0
    line_num: int = 0

    @property
    def right(self) -> int:
        return self.left + self.width

    @property
    def center_y(self) -> float:
        return self.top + self.height / 2

@dataclass
class OCRPage:
    text: str
    confidence: float
    words: List[OCRWord] = field(default_factory=list)

@dataclass
class ExtractedText:
    text: str
    pages: List[str]
    ocr_used: bool
    page_confidences: List[float] = field(default_factory=list)
    ocr_pages: List[OCRPage] = field(default_factory=list)

def extract_text(content: bytes, file_type: str) -> ExtractedText:
    """
    Extract text from PDF or image using Tesseract and PyMuPDF.
    """
    if not content:
        raise ValueError("Empty document received.")

    logger.info("Starting text extraction: type=%s size=%d", file_type, len(content))

    if file_type == "application/pdf":
        return _extract_pdf(content)
    elif file_type.startswith("image/"):
        return _extract_image(content)
    else:
        raise ValueError(f"Unsupported file type: {file_type}")

def _extract_pdf(content: bytes) -> ExtractedText:
    doc = fitz.open(stream=content, filetype="pdf")
    pages_text: list[str] = []
    page_confidences: list[float] = []
    ocr_pages: list[OCRPage] = []
    ocr_used = False

    for page_idx, page in enumerate(doc, start=1):
        # First check native text
        native_text = page.get_text("text", sort=True).strip()
        if native_text and len(native_text) > 40:
            pages_text.append(native_text)
            page_confidences.append(100.0)
            ocr_pages.append(OCRPage(text=native_text, confidence=100.0, words=[]))
            continue

        # If native text is empty or minimal, render the page for Tesseract OCR.
        ocr_used = True
        pix = page.get_pixmap(dpi=150)
        img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        ocr_page = _run_tesseract_on_image(_preprocess_image(img))
        pages_text.append(ocr_page.text)
        page_confidences.append(ocr_page.confidence)
        ocr_pages.append(ocr_page)

    doc.close()
    full_text = "\n\n".join(pages_text)
    return ExtractedText(
        text=full_text,
        pages=pages_text,
        ocr_used=ocr_used,
        page_confidences=page_confidences,
        ocr_pages=ocr_pages
    )

def _extract_image(content: bytes) -> ExtractedText:
    with Image.open(io.BytesIO(content)) as img:
        img = ImageOps.exif_transpose(img).convert("RGB")
        ocr_page = _run_tesseract_on_image(_preprocess_image(img))

    return ExtractedText(
        text=ocr_page.text,
        pages=[ocr_page.text],
        ocr_used=True,
        page_confidences=[ocr_page.confidence],
        ocr_pages=[ocr_page]
    )

def _run_tesseract_on_image(image: Image.Image) -> OCRPage:
    """Run the system Tesseract engine and return structured OCR evidence."""
    try:
        import pytesseract
        from pytesseract import Output

        data = pytesseract.image_to_data(
            image,
            config="--oem 3 --psm 6",
            output_type=Output.DICT,
            timeout=45,
        )
    except Exception:
        logger.exception("Tesseract fallback failed.")
        return OCRPage(text="", confidence=0.0, words=[])

    words: list[OCRWord] = []
    lines: dict[tuple[int, int], list[OCRWord]] = {}
    confidences: list[float] = []
    for idx, raw_text in enumerate(data.get("text", [])):
        text = raw_text.strip()
        try:
            confidence = float(data["conf"][idx])
        except (KeyError, TypeError, ValueError):
            confidence = 0.0
        if not text or confidence < 0:
            continue
        word = OCRWord(
            text=text,
            confidence=round(confidence, 2),
            left=int(data["left"][idx]),
            top=int(data["top"][idx]),
            width=int(data["width"][idx]),
            height=int(data["height"][idx]),
            block_num=int(data["block_num"][idx]),
            par_num=int(data["par_num"][idx]),
            line_num=int(data["line_num"][idx]),
        )
        words.append(word)
        lines.setdefault((word.block_num, word.par_num, word.line_num), []).append(word)
        confidences.append(confidence)

    text_lines = []
    for line in lines.values():
        ordered = sorted(line, key=lambda item: item.left)
        chunks = [[ordered[0]]] if ordered else []
        for word in ordered[1:]:
            previous = chunks[-1][-1]
            gap = word.left - previous.right
            # Preserve invoice columns such as Bill From / Bill To in the header.
            if ordered[0].top < image.height * 0.55 and gap > max(120, image.width * 0.18):
                chunks.append([word])
            else:
                chunks[-1].append(word)
        text_lines.extend(" ".join(word.text for word in chunk) for chunk in chunks)
    return OCRPage(
        text="\n".join(text_lines),
        confidence=round(sum(confidences) / len(confidences), 2) if confidences else 0.0,
        words=sorted(words, key=lambda item: (item.top, item.left)),
    )