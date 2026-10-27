"""Document upload, processing, and deletion services.

Responsibilities:
* Validate uploads (extension, size, emptiness) before touching the database.
* Store files under a private, per-user directory using server-generated,
  collision-free names (never user-supplied paths) to prevent path traversal.
* Extract text, chunk it, and persist chunks - all inside a transaction so a
  processing failure never leaves inconsistent records.
"""
from __future__ import annotations

import logging
import os
import uuid

from django.conf import settings
from django.db import transaction

from ai_assistant.services.chunking import build_chunks
from ai_assistant.services.extraction import ExtractionError, extract_text

from .models import Document, DocumentChunk

logger = logging.getLogger("documind")


class UploadValidationError(Exception):
    """Raised for uploads that are rejected before any storage occurs."""


def _detect_file_type(filename: str) -> str:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in settings.ALLOWED_UPLOAD_EXTENSIONS:
        allowed = ", ".join(e.upper() for e in settings.ALLOWED_UPLOAD_EXTENSIONS)
        raise UploadValidationError(
            f"Unsupported file type \".{ext or '?'}\". Allowed: {allowed}."
        )
    return ext


def validate_upload(uploaded_file) -> str:
    """Validate an in-memory/temporary uploaded file. Returns the file type."""
    if uploaded_file is None:
        raise UploadValidationError("No file was selected.")

    file_type = _detect_file_type(uploaded_file.name)

    size = uploaded_file.size
    if size == 0:
        raise UploadValidationError("The selected file is empty.")
    if size > settings.MAX_UPLOAD_SIZE_BYTES:
        raise UploadValidationError(
            f"The file exceeds the {settings.MAX_UPLOAD_SIZE_MB} MB limit."
        )
    return file_type


def _user_storage_dir(user) -> str:
    """Relative storage directory for a user (under PRIVATE_STORAGE_ROOT)."""
    return f"user_{user.id}"


def _save_file(user, uploaded_file, file_type) -> tuple[str, str]:
    """Write the upload to private storage; return (stored_filename, rel_path)."""
    stored_filename = f"{uuid.uuid4().hex}.{file_type}"
    rel_dir = _user_storage_dir(user)
    rel_path = f"{rel_dir}/{stored_filename}"

    abs_dir = os.path.join(settings.PRIVATE_STORAGE_ROOT, rel_dir)
    os.makedirs(abs_dir, exist_ok=True)
    abs_path = os.path.join(settings.PRIVATE_STORAGE_ROOT, rel_path)

    with open(abs_path, "wb") as destination:
        for chunk in uploaded_file.chunks():
            destination.write(chunk)
    return stored_filename, rel_path


def _sanitize_original_name(name: str) -> str:
    # Keep only the base name; never trust directory components from the client.
    return os.path.basename(name)[:255]


def process_upload(user, workspace, uploaded_file) -> Document:
    """Validate, store, and process an uploaded document.

    Raises UploadValidationError for rejected uploads (nothing is persisted).
    Returns the created Document; on extraction failure the document is saved
    with status=FAILED and a user-safe error message (no orphaned files).
    """
    file_type = validate_upload(uploaded_file)
    stored_filename, rel_path = _save_file(user, uploaded_file, file_type)
    abs_path = os.path.join(settings.PRIVATE_STORAGE_ROOT, rel_path)

    document = Document.objects.create(
        owner=user,
        workspace=workspace,
        original_filename=_sanitize_original_name(uploaded_file.name),
        stored_filename=stored_filename,
        storage_path=rel_path,
        file_type=file_type,
        file_size=uploaded_file.size,
        status=Document.Status.PROCESSING,
    )

    try:
        extraction = extract_text(abs_path, file_type)
        chunks = build_chunks(extraction)
        if not chunks:
            raise ExtractionError("No usable text could be extracted.")

        with transaction.atomic():
            DocumentChunk.objects.bulk_create(
                [
                    DocumentChunk(
                        document=document,
                        owner=user,
                        seq=chunk.seq,
                        text=chunk.text,
                        page_number=chunk.page_number,
                        reference=chunk.reference,
                    )
                    for chunk in chunks
                ]
            )
            document.status = Document.Status.READY
            document.char_count = extraction.char_count
            document.page_count = extraction.page_count
            document.chunk_count = len(chunks)
            document.error_message = ""
            document.save(
                update_fields=[
                    "status",
                    "char_count",
                    "page_count",
                    "chunk_count",
                    "error_message",
                ]
            )
    except ExtractionError as exc:
        document.status = Document.Status.FAILED
        document.error_message = str(exc)
        document.save(update_fields=["status", "error_message"])
        logger.info("Document %s processing failed: %s", document.id, exc)
    except Exception as exc:  # pragma: no cover - unexpected processing error
        document.status = Document.Status.FAILED
        document.error_message = "An unexpected error occurred during processing."
        document.save(update_fields=["status", "error_message"])
        logger.exception("Unexpected error processing document %s", document.id)

    return document


def delete_document(document: Document) -> None:
    """Delete a document, its chunks, and its stored file safely.

    Related AIRequest history is retained (FK is SET_NULL) with the document
    name preserved on each request record.
    """
    abs_path = document.absolute_path
    # Remove DB rows first (chunks cascade); file removal is best-effort after.
    document.delete()
    try:
        if abs_path.exists():
            abs_path.unlink()
    except OSError as exc:  # pragma: no cover
        logger.warning("Could not remove stored file %s: %s", abs_path, exc)
