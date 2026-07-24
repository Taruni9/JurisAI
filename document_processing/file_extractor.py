"""
Unified document extraction.

Returns a structured representation so the rest of the app can cite
"Page X, Paragraph Y" instead of just returning a wall of text.

Structure returned by extract_structured():

{
    "full_text": "...",
    "pages": [
        {
            "page": 1,
            "paragraphs": ["para 1 text", "para 2 text", ...]
        },
        ...
    ],
    "used_ocr": bool
}
"""

import io
import os
import tempfile

import pdfplumber
import pytesseract
from PIL import Image
from docx import Document as DocxDocument

try:
    from pdf2image import convert_from_path
except ImportError:  # pragma: no cover
    convert_from_path = None


SUPPORTED_EXTENSIONS = ["pdf", "docx", "txt", "png", "jpg", "jpeg"]


def _split_paragraphs(text):
    """Split a block of text into paragraphs on blank lines."""
    if not text:
        return []
    raw_paragraphs = [p.strip() for p in text.split("\n\n")]
    paragraphs = [p for p in raw_paragraphs if p]
    if len(paragraphs) <= 1 and text.strip():
        # No (or only one) blank-line break found — common in OCR output
        # and in some PDF text layers that use single newlines between
        # lines. Fall back to single-newline splitting so we still get
        # paragraph-level granularity for citations.
        single_line_split = [p.strip() for p in text.split("\n") if p.strip()]
        if len(single_line_split) > 1:
            paragraphs = single_line_split
    return paragraphs


def _ocr_pdf(file_bytes):
    """OCR a scanned PDF (no extractable text layer) page by page."""
    if convert_from_path is None:
        return []

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(file_bytes)
        tmp_path = tmp.name

    try:
        images = convert_from_path(tmp_path)
    finally:
        os.remove(tmp_path)

    pages = []
    for i, image in enumerate(images):
        text = pytesseract.image_to_string(image)
        pages.append({
            "page": i + 1,
            "paragraphs": _split_paragraphs(text)
        })
    return pages


def _extract_pdf(uploaded_file):
    file_bytes = uploaded_file.read()
    uploaded_file.seek(0)

    pages = []
    has_text = False

    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for i, page in enumerate(pdf.pages):
            page_text = page.extract_text() or ""
            if page_text.strip():
                has_text = True
            pages.append({
                "page": i + 1,
                "paragraphs": _split_paragraphs(page_text)
            })

    used_ocr = False

    # Scanned PDF with no extractable text layer — fall back to OCR.
    if not has_text:
        ocr_pages = _ocr_pdf(file_bytes)
        if ocr_pages:
            pages = ocr_pages
            used_ocr = True

    return pages, used_ocr


def _extract_docx(uploaded_file):
    doc = DocxDocument(uploaded_file)
    paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
    # DOCX has no reliable page boundaries once extracted as text, so the
    # whole document is treated as a single logical "page" and citations
    # fall back to paragraph numbers only.
    pages = [{"page": 1, "paragraphs": paragraphs}]
    return pages, False


def _extract_txt(uploaded_file):
    raw = uploaded_file.read()
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8", errors="ignore")
    pages = [{"page": 1, "paragraphs": _split_paragraphs(raw)}]
    return pages, False


def _extract_image(uploaded_file):
    image = Image.open(uploaded_file)
    text = pytesseract.image_to_string(image)
    pages = [{"page": 1, "paragraphs": _split_paragraphs(text)}]
    return pages, True


def extract_structured(uploaded_file):
    """
    Extract text from an uploaded file (PDF, DOCX, TXT, or image),
    preserving page/paragraph structure for later citation.
    """
    filename = uploaded_file.name
    ext = filename.rsplit(".", 1)[-1].lower()

    if ext == "pdf":
        pages, used_ocr = _extract_pdf(uploaded_file)
    elif ext == "docx":
        pages, used_ocr = _extract_docx(uploaded_file)
    elif ext == "txt":
        pages, used_ocr = _extract_txt(uploaded_file)
    elif ext in ("png", "jpg", "jpeg"):
        pages, used_ocr = _extract_image(uploaded_file)
    else:
        raise ValueError(f"Unsupported file type: .{ext}")

    full_text_parts = []
    for page in pages:
        full_text_parts.extend(page["paragraphs"])
    full_text = "\n\n".join(full_text_parts)

    return {
        "full_text": full_text,
        "pages": pages,
        "used_ocr": used_ocr,
        "filename": filename
    }


# ---- Backward-compatible helper (old call sites expect plain text) ----

def extract_text_from_pdf(uploaded_file):
    """Kept for backward compatibility with existing call sites."""
    return extract_structured(uploaded_file)["full_text"]
