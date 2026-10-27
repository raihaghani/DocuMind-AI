"""Document text extraction.

Extracts plain text from PDF (via PyMuPDF) and TXT files while preserving
source references (page numbers for PDFs). Raises `ExtractionError` with a
user-safe message for any condition that prevents producing usable text.
"""
from __future__ import annotations

from dataclasses import dataclass, field


class ExtractionError(Exception):
    """Raised when a document cannot be turned into usable text."""


@dataclass
class ExtractedSegment:
    """A unit of extracted text with its source reference."""

    text: str
    page_number: int | None = None  # 1-based for PDFs, None for TXT


@dataclass
class ExtractionResult:
    segments: list[ExtractedSegment] = field(default_factory=list)
    page_count: int = 0

    @property
    def full_text(self) -> str:
        return "\n\n".join(s.text for s in self.segments if s.text.strip())

    @property
    def char_count(self) -> int:
        return len(self.full_text)


def extract_text(path, file_type: str) -> ExtractionResult:
    """Dispatch extraction by file type."""
    if file_type == "pdf":
        return _extract_pdf(path)
    if file_type == "txt":
        return _extract_txt(path)
    raise ExtractionError(f"Unsupported file type: {file_type}")


def _extract_pdf(path) -> ExtractionResult:
    try:
        import fitz  # PyMuPDF
    except ImportError as exc:  # pragma: no cover - environment misconfig
        raise ExtractionError("PDF support is not available on the server.") from exc

    result = ExtractionResult()
    try:
        with fitz.open(path) as doc:
            if doc.is_encrypted:
                # Try an empty password; bail out if still locked.
                if not doc.authenticate(""):
                    raise ExtractionError(
                        "This PDF is password-protected and cannot be read."
                    )
            result.page_count = doc.page_count
            for index in range(doc.page_count):
                page = doc.load_page(index)
                text = page.get_text("text") or ""
                result.segments.append(
                    ExtractedSegment(text=text, page_number=index + 1)
                )
    except ExtractionError:
        raise
    except Exception as exc:  # corrupted / unreadable PDF
        raise ExtractionError(
            "The PDF appears to be corrupted or could not be opened."
        ) from exc

    if not result.full_text.strip():
        raise ExtractionError(
            "No selectable text was found. Scanned/image-only PDFs are not "
            "supported in this version (OCR is not available)."
        )
    return result


def _extract_txt(path) -> ExtractionResult:
    raw = _read_bytes(path)
    if not raw.strip():
        raise ExtractionError("The file is empty.")

    text = _decode_text(raw)
    if not text.strip():
        raise ExtractionError("The document contains only whitespace.")

    # Record a line-range reference per segment (whole file as one logical unit;
    # chunking later subdivides it while preserving approximate line refs).
    result = ExtractionResult(page_count=0)
    result.segments.append(ExtractedSegment(text=text, page_number=None))
    return result


def _read_bytes(path) -> bytes:
    try:
        with open(path, "rb") as handle:
            return handle.read()
    except OSError as exc:
        raise ExtractionError("The file could not be read from storage.") from exc


def _decode_text(raw: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "utf-16", "latin-1"):
        try:
            return raw.decode(encoding)
        except (UnicodeDecodeError, LookupError):
            continue
    raise ExtractionError(
        "The text file uses an unsupported character encoding."
    )
