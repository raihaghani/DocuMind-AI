"""Text chunking.

Splits extracted text into overlapping, retrieval-sized chunks while
preserving source references (page numbers for PDFs, line ranges for TXT).

Defaults (~1000 chars with ~150 overlap) are documented in
docs/engineering-decisions.md. Very short documents are kept as a single chunk
rather than being split unnecessarily.
"""
from __future__ import annotations

from dataclasses import dataclass

from django.conf import settings

from .extraction import ExtractionResult


@dataclass
class Chunk:
    seq: int
    text: str
    page_number: int | None = None
    reference: str = ""


def build_chunks(
    extraction: ExtractionResult,
    chunk_size: int | None = None,
    overlap: int | None = None,
) -> list[Chunk]:
    chunk_size = chunk_size or settings.CHUNK_SIZE
    overlap = overlap if overlap is not None else settings.CHUNK_OVERLAP
    if overlap >= chunk_size:
        overlap = chunk_size // 4

    chunks: list[Chunk] = []
    seq = 0
    for segment in extraction.segments:
        text = segment.text.strip("\n")
        if not text.strip():
            continue
        if segment.page_number is not None:
            # PDF page: chunk within the page, tagging each with the page number.
            for piece in _split(text, chunk_size, overlap):
                chunks.append(
                    Chunk(
                        seq=seq,
                        text=piece,
                        page_number=segment.page_number,
                        reference=f"Page {segment.page_number}",
                    )
                )
                seq += 1
        else:
            # TXT: chunk the whole text and attach approximate line ranges.
            for piece, start_line, end_line in _split_with_lines(
                text, chunk_size, overlap
            ):
                chunks.append(
                    Chunk(
                        seq=seq,
                        text=piece,
                        page_number=None,
                        reference=f"Lines {start_line}-{end_line}",
                    )
                )
                seq += 1
    return chunks


def _split(text: str, size: int, overlap: int) -> list[str]:
    text = text.strip()
    if len(text) <= size:
        return [text] if text else []
    step = max(1, size - overlap)
    pieces = []
    start = 0
    length = len(text)
    while start < length:
        end = min(start + size, length)
        # Prefer to break on whitespace near the window edge for cleaner chunks.
        if end < length:
            window = text.rfind(" ", start + step, end)
            if window != -1 and window > start:
                end = window
        piece = text[start:end].strip()
        if piece:
            pieces.append(piece)
        if end >= length:
            break
        start = max(end - overlap, start + 1)
    return pieces


def _split_with_lines(text: str, size: int, overlap: int):
    """Yield (chunk_text, start_line, end_line) for TXT content."""
    # Map character offsets to 1-based line numbers.
    line_starts = [0]
    for i, char in enumerate(text):
        if char == "\n":
            line_starts.append(i + 1)

    def line_at(offset: int) -> int:
        # Binary-search-free simple scan is fine for MVP document sizes.
        line = 1
        for idx, start in enumerate(line_starts):
            if start > offset:
                break
            line = idx + 1
        return line

    pieces = _split(text, size, overlap)
    results = []
    search_from = 0
    for piece in pieces:
        start_offset = text.find(piece[:40], search_from)
        if start_offset == -1:
            start_offset = search_from
        end_offset = start_offset + len(piece)
        results.append((piece, line_at(start_offset), line_at(end_offset)))
        search_from = start_offset + max(1, len(piece) - overlap)
    return results
