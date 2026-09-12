from __future__ import annotations

import io
import logging
from dataclasses import dataclass, field
from typing import List, Optional
import fitz # PyMuPDF
import numpy as np
from PIL import Image, ImageEnhance, ImageFilter, ImageOps

logger = logging.getLogger(__name__)

# Global cached EasyOCR Reader instance
_EASYOCR_READER = None

def get_ocr_reader():
    global _EASYOCR_READER
    if _EASYOCR_READER is None:
        try:
            import easyocr
            logger.info("Initializing EasyOCR reader (en, gpu=False)...")
            _EASYOCR_READER = easyocr.Reader(['en'], gpu=False, verbose=False)
        except Exception as e:
            logger.error("Failed to load EasyOCR reader: %s", e, exc_info=True)
            return None
    return _EASYOCR_READER


def _preprocess_image(image: Image.Image) -> Image.Image:
    """Normalize low-quality receipts without destroying printed characters."""
    image = ImageOps.exif_transpose(image).convert("L")
    image = ImageOps.autocontrast(image)
    image = image.filter(ImageFilter.MedianFilter(size=3))
    if max(image.size) < 1800:
        scale = 1800 / max(image.size)
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
    Extract text from PDF or image using EasyOCR and PyMuPDF.
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

    reader = get_ocr_reader()

    for page_idx, page in enumerate(doc, start=1):
        # First check native text
        native_text = page.get_text("text", sort=True).strip()
        if native_text and len(native_text) > 40:
            pages_text.append(native_text)
            page_confidences.append(100.0)
            ocr_pages.append(OCRPage(text=native_text, confidence=100.0, words=[]))
            continue

        # If native text is empty or minimal, render page to image for EasyOCR
        ocr_used = True
        pix = page.get_pixmap(dpi=200)
        img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        ocr_page = _run_easyocr_on_image(img, reader)
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
        reader = get_ocr_reader()
        ocr_page = _run_easyocr_on_image(img, reader)

    return ExtractedText(
        text=ocr_page.text,
        pages=[ocr_page.text],
        ocr_used=True,
        page_confidences=[ocr_page.confidence],
        ocr_pages=[ocr_page]
    )

def _run_easyocr_on_image(image: Image.Image, reader) -> OCRPage:
    image = _preprocess_image(image)
    if reader is None:
        return _run_tesseract_on_image(image)

    img_np = np.array(image)
    try:
        ocr_results = reader.readtext(img_np, detail=1, paragraph=False, text_threshold=0.45, low_text=0.25)
    except Exception:
        logger.exception("EasyOCR failed; falling back to Tesseract.")
        return _run_tesseract_on_image(image)
    
    # Sort boxes top-to-bottom, left-to-right based on top-left y, x
    # Group boxes that share approximately the same Y coordinate into lines
    words: list[OCRWord] = []
    conf_scores: list[float] = []

    for item in ocr_results:
        box, text, conf = item[0], item[1].strip(), float(item[2]) * 100.0
        if not text:
            continue

        xs = [pt[0] for pt in box]
        ys = [pt[1] for pt in box]
        left, top = int(min(xs)), int(min(ys))
        width, height = int(max(xs) - left), int(max(ys) - top)

        words.append(OCRWord(
            text=text,
            confidence=round(conf, 2),
            left=left,
            top=top,
            width=width,
            height=height
        ))
        conf_scores.append(conf)

    # Sort words into natural lines
    words.sort(key=lambda w: (w.top, w.left))
    lines: list[list[OCRWord]] = []
    for w in words:
        if not lines:
            lines.append([w])
        else:
            # Check if w fits into last line
            last_line = lines[-1]
            avg_y = sum(item.center_y for item in last_line) / len(last_line)
            avg_h = sum(item.height for item in last_line) / len(last_line)
            if abs(w.center_y - avg_y) <= max(10, avg_h * 0.6):
                last_line.append(w)
            else:
                lines.append([w])

    # Reconstruct text lines
    text_lines = []
    for line in lines:
        line.sort(key=lambda item: item.left)
        text_lines.append(" ".join(item.text for item in line))

    full_text = "\n".join(text_lines)
    avg_confidence = round(sum(conf_scores) / len(conf_scores), 2) if conf_scores else 0.0

    return OCRPage(text=full_text, confidence=avg_confidence, words=words)


def _run_tesseract_on_image(image: Image.Image) -> OCRPage:
    """Fallback for environments where EasyOCR weights are unavailable."""
    try:
        import pytesseract
        from pytesseract import Output

        data = pytesseract.image_to_data(image, config="--oem 3 --psm 6", output_type=Output.DICT)
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

    text_lines = [" ".join(word.text for word in sorted(line, key=lambda item: item.left)) for line in lines.values()]
    return OCRPage(
        text="\n".join(text_lines),
        confidence=round(sum(confidences) / len(confidences), 2) if confidences else 0.0,
        words=sorted(words, key=lambda item: (item.top, item.left)),
    )