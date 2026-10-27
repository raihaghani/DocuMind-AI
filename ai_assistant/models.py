from django.conf import settings
from django.db import models

from documents.models import Document


class AIRequest(models.Model):
    """Persistent record of a single AI question/answer interaction."""

    class Status(models.TextChoices):
        SUCCESS = "success", "Successful"
        UNSUPPORTED = "unsupported", "Unsupported"
        FAILED = "failed", "Failed"

    class Provider(models.TextChoices):
        MOCK = "mock", "Mock"
        OPENAI = "openai", "OpenAI"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="ai_requests",
    )
    # Keep history even if the source document is later deleted.
    document = models.ForeignKey(
        Document,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ai_requests",
    )
    # Snapshot of the document name so history survives document deletion.
    document_name = models.CharField(max_length=255)
    question = models.TextField()
    answer = models.TextField(blank=True, default="")
    status = models.CharField(max_length=16, choices=Status.choices)
    provider_mode = models.CharField(max_length=16, choices=Provider.choices)
    # List of {"document": str, "page": int|null, "label": str, "snippet": str}
    sources = models.JSONField(default=list, blank=True)
    error_detail = models.CharField(max_length=255, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        return f"{self.user} @ {self.created_at:%Y-%m-%d %H:%M}: {self.question[:40]}"

    @property
    def answer_preview(self) -> str:
        preview = (self.answer or "").strip()
        return preview[:120] + ("…" if len(preview) > 120 else "")


class UsageRecord(models.Model):
    """Per-user, per-day counter of consumed AI questions.

    A unique (user, date) constraint prevents duplicate daily records, and
    counts are updated atomically (see services/usage.py) so concurrent
    requests cannot exceed the configured quota.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="usage_records",
    )
    date = models.DateField()
    count = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "date"], name="unique_usage_per_user_per_day"
            )
        ]
        indexes = [models.Index(fields=["user", "date"])]

    def __str__(self):
        return f"{self.user} {self.date}: {self.count}"
