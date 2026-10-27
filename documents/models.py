from pathlib import Path

from django.conf import settings
from django.db import models

from workspace.models import Workspace


class Document(models.Model):
    """Metadata for an uploaded document owned by a single user."""

    class Status(models.TextChoices):
        PROCESSING = "processing", "Processing"
        READY = "ready", "Ready"
        FAILED = "failed", "Failed"

    class FileType(models.TextChoices):
        PDF = "pdf", "PDF"
        TXT = "txt", "Text"

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="documents",
    )
    workspace = models.ForeignKey(
        Workspace,
        on_delete=models.CASCADE,
        related_name="documents",
    )
    original_filename = models.CharField(max_length=255)
    # Server-generated, collision-free name used on disk (never user-supplied).
    stored_filename = models.CharField(max_length=255)
    # Path relative to settings.PRIVATE_STORAGE_ROOT.
    storage_path = models.CharField(max_length=512)
    file_type = models.CharField(max_length=8, choices=FileType.choices)
    file_size = models.PositiveIntegerField(default=0)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.PROCESSING,
    )
    char_count = models.PositiveIntegerField(default=0)
    page_count = models.PositiveIntegerField(default=0)
    chunk_count = models.PositiveIntegerField(default=0)
    error_message = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["-uploaded_at"]
        indexes = [
            models.Index(fields=["owner", "-uploaded_at"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        return f"{self.original_filename} ({self.owner})"

    @property
    def absolute_path(self) -> Path:
        """Absolute filesystem path to the stored file."""
        return Path(settings.PRIVATE_STORAGE_ROOT) / self.storage_path

    @property
    def is_ready(self) -> bool:
        return self.status == self.Status.READY

    @property
    def size_display(self) -> str:
        size = self.file_size
        for unit in ("B", "KB", "MB"):
            if size < 1024 or unit == "MB":
                return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} MB"


class DocumentChunk(models.Model):
    """A searchable text chunk extracted from a document.

    `owner` is denormalized from the parent document so that retrieval queries
    can enforce user isolation directly at the chunk level.
    """

    document = models.ForeignKey(
        Document,
        on_delete=models.CASCADE,
        related_name="chunks",
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="document_chunks",
    )
    seq = models.PositiveIntegerField(help_text="0-based chunk sequence number.")
    text = models.TextField()
    # Page number for PDFs; line-range label for TXT is stored in `reference`.
    page_number = models.PositiveIntegerField(null=True, blank=True)
    reference = models.CharField(max_length=120, blank=True, default="")

    class Meta:
        ordering = ["document_id", "seq"]
        unique_together = ("document", "seq")
        indexes = [
            models.Index(fields=["document", "seq"]),
            models.Index(fields=["owner"]),
        ]

    def __str__(self):
        return f"{self.document.original_filename} chunk #{self.seq}"

    @property
    def source_label(self) -> str:
        """Human-readable citation label, e.g. 'Page 3' or 'Lines 10-20'."""
        if self.page_number:
            return f"Page {self.page_number}"
        if self.reference:
            return self.reference
        return f"Chunk {self.seq + 1}"
